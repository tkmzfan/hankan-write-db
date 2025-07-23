import json
import zipfile
import os
from collections import defaultdict
import urllib.request

def download_unihan():
    """Download and extract Unihan database if not present"""
    zip_file = "Unihan.zip"
    extract_dir = "Unihan_data"
    
    # Check if zip file already exists
    if not os.path.exists(zip_file):
        print("Downloading Unihan database...")
        url = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
        urllib.request.urlretrieve(url, zip_file)
        print("Unihan database downloaded.")
    else:
        print("Unihan.zip already exists, skipping download.")
    
    # Check if extraction is needed
    if not os.path.exists(extract_dir):
        print("Extracting Unihan database...")
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("Unihan database extracted.")
    else:
        print("Unihan data already extracted.")
    
    return extract_dir

def parse_unihan_file(filename, field):
    """Parse a Unihan file and extract specific field data"""
    data = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3 and parts[1] == field:
                    codepoint = parts[0]
                    value = parts[2]
                    
                    # Convert Unicode codepoint to character
                    if codepoint.startswith('U+'):
                        char = chr(int(codepoint[2:], 16))
                        data[char] = value
    except FileNotFoundError:
        print(f"File {filename} not found.")
    
    return data

def generate_character_dict():
    """Generate comprehensive character dictionary"""
    unihan_dir = download_unihan()
    
    print("Parsing Unihan data...")
    
    # Parse pinyin readings from multiple sources
    pinyin_data = {}
    pinyin_sources = [
        ('Unihan_Readings.txt', 'kMandarin'),
        ('Unihan_Readings.txt', 'kHanyuPinyin')
    ]
    
    for filename, field in pinyin_sources:
        file_path = os.path.join(unihan_dir, filename)
        temp_data = parse_unihan_file(file_path, field)
        pinyin_data.update(temp_data)
        print(f"Found {len(temp_data)} pinyin entries from {field}")
    
    # Parse definitions - try multiple sources since kDefinition might be in different files
    definition_data = {}
    definition_sources = [
        ('Unihan_Readings.txt', 'kDefinition'),
        ('Unihan_DictionaryLikeData.txt', 'kDefinition'),
        ('Unihan_OtherMappings.txt', 'kDefinition')
    ]
    
    for filename, field in definition_sources:
        file_path = os.path.join(unihan_dir, filename)
        if os.path.exists(file_path):
            temp_data = parse_unihan_file(file_path, field)
            definition_data.update(temp_data)
            print(f"Found {len(temp_data)} definition entries from {filename}")
    
    # If no definitions found, inform user
    if not definition_data:
        print("Warning: No definitions found in any Unihan files.")
        print("Available files in Unihan_data directory:")
        if os.path.exists(unihan_dir):
            for file in os.listdir(unihan_dir):
                if file.endswith('.txt'):
                    print(f"  - {file}")
    
    # Combine all characters
    all_chars = set(pinyin_data.keys()) | set(definition_data.keys())
    
    # Build final dictionary
    char_dict = {}
    for char in all_chars:
        # Clean up pinyin data
        raw_pinyin = pinyin_data.get(char, '')
        clean_pinyin = ''
        if raw_pinyin:
            # Remove numbers and extra formatting, take first pronunciation
            clean_pinyin = raw_pinyin.split(',')[0].split()[0]  # Take first reading
            # Remove any remaining numbers or colons
            clean_pinyin = ''.join(c for c in clean_pinyin if not c.isdigit() and c != ':')
            clean_pinyin = clean_pinyin.strip()
        
        char_dict[char] = {
            'pinyin': clean_pinyin,
            'meaning': definition_data.get(char, '')
        }
    
    # Save to JSON
    output_file = 'chinese_characters.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(char_dict, f, ensure_ascii=False, indent=2)
    
    print(f"Generated dictionary with {len(char_dict)} characters")
    print(f"Characters with pinyin: {len([c for c in char_dict.values() if c['pinyin']])}")
    print(f"Characters with meanings: {len([c for c in char_dict.values() if c['meaning']])}")
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    generate_character_dict()