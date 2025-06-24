#!/usr/bin/env python3
"""
Dalecarlia Cup 2025 - Automatisk ansiktsbeskärning
Förenklad version med hårdkodade inställningar
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
import io
import json
from google.cloud import vision
from typing import List, Tuple, Optional

# ====================================
# INSTÄLLNINGAR - ÄNDRA HÄR
# ====================================

# Sökväg till din Google Cloud JSON-fil
GOOGLE_CREDENTIALS_PATH = "/Users/christofferlindberg/Desktop/manual/spintso-6ff83b39e712.json"

# Mappar
INPUT_DIR = "uploads"           # Mapp med originalbilder
OUTPUT_DIR = "uploads_cropped"  # Mapp för beskurna bilder
BACKUP_DIR = "uploads_backup"   # Backup av originaler

# Bildstorlek
TARGET_SIZE = 400              # Målstorlek för kvadratiska bilder (400x400)

# Inställningar
CREATE_BACKUP = True           # Skapa backup av originalbilder
OVERWRITE_EXISTING = True      # Skriv över befintliga filer i output

# ====================================

class FaceCropProcessor:
    def __init__(self):
        """Initialisera Face Crop Processor med hårdkodade inställningar"""
        
        # Sätt Google credentials
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_CREDENTIALS_PATH
        
        self.input_dir = Path(INPUT_DIR)
        self.output_dir = Path(OUTPUT_DIR)
        self.backup_dir = Path(BACKUP_DIR)
        self.size = TARGET_SIZE
        
        # Skapa mappar
        self.output_dir.mkdir(exist_ok=True)
        if CREATE_BACKUP:
            self.backup_dir.mkdir(exist_ok=True)
        
        # Kontrollera att input-mappen finns
        if not self.input_dir.exists():
            print(f"❌ Input-mappen {INPUT_DIR} finns inte!")
            sys.exit(1)
        
        # Initialisera Google Vision client
        try:
            self.vision_client = vision.ImageAnnotatorClient()
            print("✅ Google Cloud Vision API initialiserad")
        except Exception as e:
            print(f"❌ Fel vid initialisering av Google Vision API: {e}")
            print(f"💡 Kontrollera att {GOOGLE_CREDENTIALS_PATH} är korrekt")
            sys.exit(1)
    
    def get_supported_formats(self) -> List[str]:
        """Returnera lista över supporterade bildformat"""
        return ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']
    
    def find_images(self) -> List[Path]:
        """Hitta alla bildifiler i input-mappen"""
        supported_formats = self.get_supported_formats()
        images = []
        
        for file_path in self.input_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                images.append(file_path)
        
        return sorted(images)
    
    def detect_faces(self, image_path: Path) -> List[vision.FaceAnnotation]:
        """
        Använd Google Vision API för att hitta ansikten i bilden
        """
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.face_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Google Vision API error: {response.error.message}')
            
            return response.face_annotations
        
        except Exception as e:
            print(f"❌ Fel vid ansiktsdetektering för {image_path.name}: {e}")
            return []
    
    def get_crop_hints(self, image_path: Path) -> List[vision.CropHint]:
        """
        Använd Google Vision API för crop hints som fallback
        """
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Begär crop hints för kvadratisk bild
            crop_hints_params = vision.CropHintsParams(aspect_ratios=[1.0])
            image_context = vision.ImageContext(crop_hints_params=crop_hints_params)
            
            response = self.vision_client.crop_hints(image=image, image_context=image_context)
            
            if response.error.message:
                raise Exception(f'Google Vision API error: {response.error.message}')
            
            return response.crop_hints_annotation.crop_hints
        
        except Exception as e:
            print(f"❌ Fel vid crop hints för {image_path.name}: {e}")
            return []
    
    def calculate_face_crop_box(self, faces: List[vision.FaceAnnotation], 
                               image_width: int, image_height: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Beräkna optimal beskärningsbox baserat på ansikten
        """
        if not faces:
            return None
        
        # Hitta bounding box som inkluderar alla ansikten
        min_x = min_y = float('inf')
        max_x = max_y = 0
        
        for face in faces:
            vertices = face.bounding_poly.vertices
            for vertex in vertices:
                min_x = min(min_x, vertex.x)
                max_x = max(max_x, vertex.x)
                min_y = min(min_y, vertex.y)
                max_y = max(max_y, vertex.y)
        
        # Lägg till marginal runt ansikten (20% på varje sida)
        margin_x = (max_x - min_x) * 0.2
        margin_y = (max_y - min_y) * 0.2
        
        crop_left = max(0, int(min_x - margin_x))
        crop_top = max(0, int(min_y - margin_y))
        crop_right = min(image_width, int(max_x + margin_x))
        crop_bottom = min(image_height, int(max_y + margin_y))
        
        # Gör beskärningen kvadratisk
        crop_width = crop_right - crop_left
        crop_height = crop_bottom - crop_top
        
        if crop_width > crop_height:
            # Bredare än hög - utöka höjden
            diff = crop_width - crop_height
            crop_top = max(0, crop_top - diff // 2)
            crop_bottom = min(image_height, crop_bottom + diff // 2)
        else:
            # Högre än bred - utöka bredden
            diff = crop_height - crop_width
            crop_left = max(0, crop_left - diff // 2)
            crop_right = min(image_width, crop_right + diff // 2)
        
        return (crop_left, crop_top, crop_right, crop_bottom)
    
    def calculate_crop_hint_box(self, crop_hints: List[vision.CropHint], 
                               image_width: int, image_height: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Beräkna beskärningsbox baserat på Google Vision crop hints
        """
        if not crop_hints:
            return None
        
        # Använd första crop hint (högsta konfidensen)
        hint = crop_hints[0]
        vertices = hint.bounding_poly.vertices
        
        min_x = min(v.x for v in vertices)
        max_x = max(v.x for v in vertices)
        min_y = min(v.y for v in vertices)
        max_y = max(v.y for v in vertices)
        
        return (int(min_x), int(min_y), int(max_x), int(max_y))
    
    def center_crop_square(self, image_width: int, image_height: int) -> Tuple[int, int, int, int]:
        """
        Fallback: Beskär kvadratiskt från mitten av bilden
        """
        size = min(image_width, image_height)
        left = (image_width - size) // 2
        top = (image_height - size) // 2
        right = left + size
        bottom = top + size
        
        return (left, top, right, bottom)
    
    def should_process_image(self, image_path: Path) -> bool:
        """Kontrollera om bilden ska bearbetas"""
        output_path = self.output_dir / image_path.name
        
        if not OVERWRITE_EXISTING and output_path.exists():
            print(f"   ⏭️  Hoppar över (finns redan): {image_path.name}")
            return False
        
        return True
    
    def process_image(self, image_path: Path) -> bool:
        """
        Bearbeta en enskild bild - beskär till ansikte och gör kvadratisk
        """
        if not self.should_process_image(image_path):
            return True
        
        print(f"\n🖼️  Bearbetar: {image_path.name}")
        
        try:
            # Ladda originalbild
            with Image.open(image_path) as img:
                # Konvertera till RGB om nödvändigt
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                image_width, image_height = img.size
                print(f"   📏 Original storlek: {image_width}x{image_height}")
                
                # 1. Försök hitta ansikten först
                faces = self.detect_faces(image_path)
                crop_box = None
                method_used = "center"
                
                if faces:
                    print(f"   😊 Hittade {len(faces)} ansikte(n)")
                    crop_box = self.calculate_face_crop_box(faces, image_width, image_height)
                    method_used = "face"
                
                # 2. Fallback till crop hints om inga ansikten hittades
                if crop_box is None:
                    print("   🔍 Använder crop hints...")
                    crop_hints = self.get_crop_hints(image_path)
                    if crop_hints:
                        crop_box = self.calculate_crop_hint_box(crop_hints, image_width, image_height)
                        method_used = "crop_hint"
                
                # 3. Sista fallback: beskär från mitten
                if crop_box is None:
                    print("   📐 Fallback: beskär från mitten")
                    crop_box = self.center_crop_square(image_width, image_height)
                    method_used = "center"
                
                # Beskär bilden
                cropped_img = img.crop(crop_box)
                
                # Ändra storlek till målstorlek
                final_img = cropped_img.resize((self.size, self.size), Image.Resampling.LANCZOS)
                
                # Spara backup om aktiverat
                if CREATE_BACKUP:
                    backup_path = self.backup_dir / image_path.name
                    if not backup_path.exists():
                        img.save(backup_path, quality=95)
                
                # Spara beskuren bild
                output_path = self.output_dir / image_path.name
                final_img.save(output_path, quality=95, optimize=True)
                
                print(f"   ✅ Sparad som {self.size}x{self.size} ({method_used}): {output_path.name}")
                return True
                
        except Exception as e:
            print(f"   ❌ Fel vid bearbetning: {e}")
            return False
    
    def process_all_images(self) -> dict:
        """
        Bearbeta alla bilder i input-mappen
        """
        images = self.find_images()
        
        if not images:
            print(f"❌ Inga bilder hittades i {INPUT_DIR}")
            return {"processed": 0, "failed": 0, "total": 0}
        
        print(f"🎯 Hittade {len(images)} bilder att bearbeta")
        print(f"📁 Input: {INPUT_DIR}")
        print(f"📁 Output: {OUTPUT_DIR}")
        print(f"📐 Målstorlek: {TARGET_SIZE}x{TARGET_SIZE}")
        
        if CREATE_BACKUP:
            print(f"💾 Backup: {BACKUP_DIR}")
        
        processed = 0
        failed = 0
        
        for image_path in images:
            if self.process_image(image_path):
                processed += 1
            else:
                failed += 1
        
        print(f"\n📊 SAMMANFATTNING:")
        print(f"   ✅ Lyckade: {processed}")
        print(f"   ❌ Misslyckade: {failed}")
        print(f"   📋 Totalt: {len(images)}")
        
        return {
            "processed": processed,
            "failed": failed,
            "total": len(images)
        }

def main():
    """Huvudfunktion"""
    print("🎭 Dalecarlia Cup 2025 - Automatisk Ansiktsbeskärning")
    print("=" * 50)
    
    processor = FaceCropProcessor()
    stats = processor.process_all_images()
    
    if stats["processed"] > 0:
        print(f"\n🎉 Klart! {stats['processed']} bilder beskurna och sparade i {OUTPUT_DIR}")
        print(f"💡 Nästa steg: Uppdatera server.js att använda {OUTPUT_DIR} eller kopiera tillbaka till {INPUT_DIR}")
    else:
        print("\n😞 Inga bilder kunde bearbetas")

if __name__ == "__main__":
    main()