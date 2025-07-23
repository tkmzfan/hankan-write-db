import json
import sqlite3
import urllib.request
import zipfile
import os

def download_unihan_data():
    """Download the Unihan database from Unicode.org"""
    url = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
    zip_filename = "Unihan.zip"
    
    if not os.path.exists(zip_filename):
        print("Downloading Unihan database...")
        urllib.request.urlretrieve(url, zip_filename)
        print("Download complete.")
    
    # Extract the zip file
    with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
        zip_ref.extractall("Unihan_data")
    
    return "Unihan_data"

def parse_unihan_file(file_path, field_name):
    """Parse a Unihan data file and extract character data"""
    data = {}
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} not found")
        return data
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 3 and parts[1] == field_name:
                unicode_point = parts[0]
                value = parts[2]
                
                # Convert Unicode code point to character
                if unicode_point.startswith('U+'):
                    code_point = int(unicode_point[2:], 16)
                    char = chr(code_point)
                    data[char] = value
    
    return data

def is_simplified_chinese(char):
    """Check if character is in simplified Chinese range"""
    code_point = ord(char)
    # CJK Unified Ideographs: 4E00-9FFF
    # CJK Extension A: 3400-4DBF
    return 0x4E00 <= code_point <= 0x9FFF or 0x3400 <= code_point <= 0x4DBF

def setup_database():
    """Create and populate the database with full Unihan data"""
    conn = sqlite3.connect('chinese_chars.db')
    cursor = conn.cursor()
    
    # Drop existing table to ensure clean schema
    cursor.execute('DROP TABLE IF EXISTS characters')
    
    # Create table with correct schema
    cursor.execute('''
        CREATE TABLE characters (
            char TEXT PRIMARY KEY,
            stroke_count INTEGER,
            is_simplified BOOLEAN,
            traditional_variant TEXT,
            simplified_variant TEXT,
            definition TEXT,
            pinyin TEXT
        )
    ''')
    
    # Download Unihan data
    unihan_dir = download_unihan_data()
    
    # Parse relevant Unihan files
    print("Parsing Unihan data...")
    
    # Get stroke counts - try multiple files and don't break after first
    stroke_data = {}
    stroke_files = [
        ("Unihan_DictionaryIndices.txt", "kTotalStrokes"),
        ("Unihan_DictionaryLikeData.txt", "kTotalStrokes"),
        ("Unihan_IRGSources.txt", "kTotalStrokes"),
        ("Unihan_NumericValues.txt", "kTotalStrokes")
    ]
    
    for filename, field in stroke_files:
        file_path = os.path.join(unihan_dir, filename)
        if os.path.exists(file_path):
            print(f"Parsing stroke data from {filename}")
            temp_data = parse_unihan_file(file_path, field)
            stroke_data.update(temp_data)
            print(f"Found {len(temp_data)} stroke entries in {filename}")
    
    print(f"Total stroke data entries: {len(stroke_data)}")
    
    # Get simplified/traditional variants
    simplified_data = parse_unihan_file(
        os.path.join(unihan_dir, "Unihan_Variants.txt"), 
        "kSimplifiedVariant"
    )
    
    traditional_data = parse_unihan_file(
        os.path.join(unihan_dir, "Unihan_Variants.txt"), 
        "kTraditionalVariant"
    )
    
    # Get definitions
    definition_data = parse_unihan_file(
        os.path.join(unihan_dir, "Unihan_Readings.txt"), 
        "kDefinition"
    )
    
    # Get Pinyin readings - try multiple sources
    pinyin_data = {}
    pinyin_sources = [
        ("Unihan_Readings.txt", "kMandarin"),
        ("Unihan_Readings.txt", "kHanyuPinyin")
    ]
    
    for filename, field in pinyin_sources:
        file_path = os.path.join(unihan_dir, filename)
        temp_data = parse_unihan_file(file_path, field)
        pinyin_data.update(temp_data)
    
    # Combine all data sources
    all_chars = set()
    all_chars.update(stroke_data.keys())
    all_chars.update(simplified_data.keys())
    all_chars.update(traditional_data.keys())
    all_chars.update(definition_data.keys())
    all_chars.update(pinyin_data.keys())
    
    print(f"Processing {len(all_chars)} characters...")
    
    processed_data = []
    for char in all_chars:
        if is_simplified_chinese(char):
            # Parse stroke count safely
            stroke_count = None
            if char in stroke_data and stroke_data[char]:
                try:
                    # Handle multiple stroke counts (sometimes space-separated)
                    stroke_str = stroke_data[char].strip()
                    if ' ' in stroke_str:
                        stroke_str = stroke_str.split()[0]
                    stroke_count = int(stroke_str)
                except (ValueError, IndexError):
                    print(f"Could not parse stroke count for {char}: {stroke_data[char]}")
                    stroke_count = None
            
            # Better classification logic - determine character type
            has_simplified_variant = char in simplified_data and simplified_data[char] != char
            has_traditional_variant = char in traditional_data and traditional_data[char] != char
            
            # Character types:
            # 0 = Traditional-only (has simplified variant)
            # 1 = Simplified-only (has traditional variant)
            # 2 = Common (no variants, used in both)
            
            if has_simplified_variant:
                char_type = 0  # Traditional-only
            elif has_traditional_variant:
                char_type = 1  # Simplified-only
            else:
                char_type = 2  # Common to both
            
            traditional_variant = traditional_data.get(char, '')
            simplified_variant = simplified_data.get(char, '')
            definition = definition_data.get(char, '')
            pinyin = pinyin_data.get(char, '')
            
            # Clean up pinyin data (remove tone numbers for cleaner output)
            if pinyin:
                pinyin = pinyin.split()[0]  # Take first pronunciation if multiple
            
            processed_data.append((
                char, 
                stroke_count, 
                char_type,  # Store character type instead of boolean
                traditional_variant,
                simplified_variant,
                definition,
                pinyin
            ))
    
    print(f"Inserting {len(processed_data)} characters into database...")
    
    cursor.executemany('''
        INSERT INTO characters 
        (char, stroke_count, is_simplified, traditional_variant, simplified_variant, definition, pinyin) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', processed_data)
    
    conn.commit()
    conn.close()
    
    print("Database setup complete!")

def get_characters_from_db():
    """Retrieve characters for simplified Chinese (simplified-only + common)"""
    conn = sqlite3.connect('chinese_chars.db')
    cursor = conn.cursor()
    
    # Query: simplified-only (1) + common (2) characters with stroke count
    cursor.execute('''
        SELECT char FROM characters 
        WHERE is_simplified IN (1, 2) AND stroke_count IS NOT NULL
        ORDER BY stroke_count ASC, char ASC
    ''')
    
    characters = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return characters

def get_traditional_characters_from_db():
    """Retrieve characters for traditional Chinese (traditional-only + common)"""
    conn = sqlite3.connect('chinese_chars.db')
    cursor = conn.cursor()
    
    # Query: traditional-only (0) + common (2) characters with stroke count
    cursor.execute('''
        SELECT char FROM characters 
        WHERE is_simplified IN (0, 2) AND stroke_count IS NOT NULL
        ORDER BY stroke_count ASC, char ASC
    ''')
    
    characters = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return characters

def debug_database():
    """Debug function to see what's in the database"""
    conn = sqlite3.connect('chinese_chars.db')
    cursor = conn.cursor()
    
    # Check total characters
    cursor.execute('SELECT COUNT(*) FROM characters')
    total = cursor.fetchone()[0]
    print(f"Total characters in database: {total}")
    
    # Check how many have stroke counts
    cursor.execute('SELECT COUNT(*) FROM characters WHERE stroke_count IS NOT NULL')
    with_strokes = cursor.fetchone()[0]
    print(f"Characters with stroke counts: {with_strokes}")
    
    # Check character types
    cursor.execute('SELECT COUNT(*) FROM characters WHERE is_simplified = 0')
    traditional_only = cursor.fetchone()[0]
    print(f"Traditional-only characters: {traditional_only}")
    
    cursor.execute('SELECT COUNT(*) FROM characters WHERE is_simplified = 1') 
    simplified_only = cursor.fetchone()[0]
    print(f"Simplified-only characters: {simplified_only}")
    
    cursor.execute('SELECT COUNT(*) FROM characters WHERE is_simplified = 2')
    common = cursor.fetchone()[0]
    print(f"Common characters (both sets): {common}")
    
    # Check final counts for each set
    cursor.execute('SELECT COUNT(*) FROM characters WHERE is_simplified IN (1, 2) AND stroke_count IS NOT NULL')
    simplified_set = cursor.fetchone()[0]
    print(f"Simplified set (simplified-only + common): {simplified_set}")
    
    cursor.execute('SELECT COUNT(*) FROM characters WHERE is_simplified IN (0, 2) AND stroke_count IS NOT NULL') 
    traditional_set = cursor.fetchone()[0]
    print(f"Traditional set (traditional-only + common): {traditional_set}")
    
    conn.close()

def main():
    try:
        # Setup database with full Unihan data (run this once or when updating)
        setup_database()
        
        # Debug the database
        debug_database()
        
        # Get sorted characters from database
        simplified_chars = get_characters_from_db()
        traditional_chars = get_traditional_characters_from_db()
        
        # Output simplified characters to JSON file
        with open('simplified_chars_by_stroke.json', 'w', encoding='utf-8') as f:
            json.dump(simplified_chars, f, ensure_ascii=False, indent=2)
        
        # Output traditional characters to JSON file
        with open('traditional_chars_by_stroke.json', 'w', encoding='utf-8') as f:
            json.dump(traditional_chars, f, ensure_ascii=False, indent=2)
        
        print(f"Generated simplified JSON file with {len(simplified_chars)} characters")
        print(f"Generated traditional JSON file with {len(traditional_chars)} characters")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()