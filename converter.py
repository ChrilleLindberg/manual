#!/usr/bin/env python3
"""
Konverterar CSV-fil till JavaScript array för Dalecarlia Cup domarkatalog
"""

import csv
import os
from pathlib import Path

# INSTÄLLNINGAR
CSV_FILE = "data/manifest.csv"  # Din CSV-fil
IMAGES_DIR = "uploads"  # Mapp med bilder (eller uploads)
OUTPUT_FILE = "domardata.js"   # Output JavaScript-fil

def clean_filename(name):
    """Konvertera namn till filnamn-format"""
    return name.lower().replace(" ", "-").replace("å", "a").replace("ä", "a").replace("ö", "o")

def find_matching_image(name, images_dir):
    """Hitta matchande bildfil för namnet"""
    if not os.path.exists(images_dir):
        return f"images/{clean_filename(name)}.jpg"
    
    # Lista alla bildfiler
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        image_files.extend(Path(images_dir).glob(f"*{ext}"))
    
    # Testa olika namnvariationer
    name_variations = [
        name,  # Exakt namn
        name.lower(),  # Lowercase
        clean_filename(name),  # Formaterat namn
        name.replace(" ", ""),  # Utan mellanslag
        name.replace(" ", "_"),  # Med understreck
    ]
    
    for image_file in image_files:
        file_stem = image_file.stem.lower()
        for variation in name_variations:
            if file_stem == variation.lower():
                return f"images/{image_file.name}"
    
    # Fallback - gissa filnamn
    return f"images/{clean_filename(name)}.jpg"

def convert_csv_to_js():
    """Huvudfunktion för konvertering"""
    print("🔄 Konverterar CSV till JavaScript array...")
    print(f"📁 CSV-fil: {CSV_FILE}")
    print(f"🖼️  Bildmapp: {IMAGES_DIR}")
    
    if not os.path.exists(CSV_FILE):
        print(f"❌ Kan inte hitta CSV-filen: {CSV_FILE}")
        print("💡 Kontrollera sökvägen eller ändra CSV_FILE i scriptet")
        return
    
    js_lines = []
    total_rows = 0
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as file:
            # Försök identifiera delimiter automatiskt
            sample = file.read(1024)
            file.seek(0)
            
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(file, delimiter=delimiter)
            
            print(f"📋 CSV-kolumner hittade: {reader.fieldnames}")
            
            for row in reader:
                # Testa olika kolumnnamn som kan finnas
                name = (row.get('Name') or row.get('Namn') or 
                       row.get('name') or row.get('namn') or '').strip()
                
                phone = (row.get('Phone') or row.get('Telefon') or 
                        row.get('phone') or row.get('telefon') or '').strip()
                
                domarnr = (row.get('Domarnummer') or row.get('DomarNr') or 
                          row.get('domarnummer') or row.get('Nr') or 
                          row.get('Number') or '').strip()
                
                if not name:  # Hoppa över tomma rader
                    continue
                
                # Hitta matchande bild
                image_path = find_matching_image(name, IMAGES_DIR)
                
                # Skapa JavaScript array-rad
                js_line = f'  ["{name}", "{phone}", "{domarnr}", "{image_path}"]'
                js_lines.append(js_line)
                total_rows += 1
                
                # Visa progress var 50:e rad
                if total_rows % 50 == 0:
                    print(f"   Bearbetat {total_rows} rader...")
    
    except Exception as e:
        print(f"❌ Fel vid läsning av CSV: {e}")
        return
    
    # Skapa JavaScript-fil
    js_content = f"""// Domardata för Dalecarlia Cup 2025
// Genererad automatiskt från {CSV_FILE}
// Totalt {total_rows} domare

const domarData = [
{chr(10).join(js_lines)}
];

// Export för användning
if (typeof module !== 'undefined' && module.exports) {{
    module.exports = domarData;
}}
"""
    
    # Spara JavaScript-fil
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"\n✅ Konvertering klar!")
    print(f"📄 JavaScript-fil skapad: {OUTPUT_FILE}")
    print(f"👥 Totalt domare: {total_rows}")
    print(f"\n📋 Nästa steg:")
    print(f"1. Kopiera innehållet från {OUTPUT_FILE}")
    print(f"2. Ersätt exempel-data i din index.html")
    print(f"3. Kopiera bilder från {IMAGES_DIR} till images/ i ditt Vercel-projekt")
    print(f"4. Deploy igen till Vercel")
    
    # Visa första 5 rader som exempel
    print(f"\n🔍 Första 5 raderna:")
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[4:9]):  # Hoppa headers, visa första 5 data-rader
            print(f"   {line.strip()}")

if __name__ == "__main__":
    convert_csv_to_js()