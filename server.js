// server.js - Node.js/Express backend
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs').promises;
const csv = require('csv-parser');
const { createReadStream } = require('fs');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Multer setup for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/');
  },
  filename: (req, file, cb) => {
    const nameWithoutExt = path.parse(file.originalname).name;
    cb(null, nameWithoutExt + path.extname(file.originalname));
  }
});

const upload = multer({ storage: storage });

// In-memory databas
let domarData = [];

// Läs CSV-fil vid start
async function loadDataFromCSV() {
  try {
    domarData = [];
    createReadStream('data/manifest.csv')
      .pipe(csv())
      .on('data', (row) => {
        domarData.push({
          name: row.Name || row.Namn,
          phone: row.Phone || row.Telefon,
          domarnummer: row.Domarnummer || row.DomarNr,
          fileId: row.FileId || '',
          imagePath: null
        });
      })
      .on('end', () => {
        console.log('📊 CSV data loaded:', domarData.length, 'records');
        console.log('First 5 names from CSV:');
        domarData.slice(0, 5).forEach((person, i) => {
          console.log(`  ${i+1}. "${person.name}"`);
        });
        syncLocalImages();
      })
      .on('error', (error) => {
        console.error('❌ Error reading CSV:', error);
      });
  } catch (error) {
    console.error('❌ Error loading CSV:', error);
  }
}

// Synka lokala bilder med data (förbättrad med debug)
async function syncLocalImages() {
  try {
    const imageFiles = await fs.readdir('uploads/');
    console.log('\n🖼️  Found image files in uploads/:');
    imageFiles.forEach((file, i) => {
      console.log(`  ${i+1}. "${file}"`);
    });
    
    console.log('\n🔍 Matching process:');
    console.log('=' .repeat(50));
    
    let matchCount = 0;
    
    domarData.forEach((person, index) => {
      const originalName = person.name;
      
      // Prova flera matchningsstrategier
      const nameVariations = [
        originalName, // Exakt som i CSV
        originalName.toLowerCase(), // bara lowercase
        originalName.toLowerCase().trim(), // lowercase + trim
        originalName.toLowerCase().replace(/\s+/g, '-'), // lowercase med bindestreck
        originalName.toLowerCase().replace(/\s+/g, ''), // lowercase utan mellanslag
        originalName.replace(/\s+/g, '-'), // bindestreck utan lowercase
        originalName.replace(/\s+/g, ''), // inga mellanslag
        originalName.trim() // bara trim
      ];
      
      console.log(`\n${index + 1}. Trying to match: "${originalName}"`);
      
      const matchingFile = imageFiles.find(file => {
        const fileNameWithoutExt = path.parse(file).name;
        
        // Testa alla variationer
        const match = nameVariations.some(variation => {
          const exactMatch = fileNameWithoutExt === variation;
          const caseInsensitiveMatch = fileNameWithoutExt.toLowerCase() === variation.toLowerCase();
          return exactMatch || caseInsensitiveMatch;
        });
        
        return match;
      });
      
      if (matchingFile) {
        person.imagePath = `/uploads/${matchingFile}`;
        person.fileId = matchingFile;
        matchCount++;
        console.log(`   ✅ MATCH: "${originalName}" -> "${matchingFile}"`);
      } else {
        console.log(`   ❌ NO MATCH for "${originalName}"`);
        
        // Visa potentiella matchningar (partial matches)
        const partialMatches = imageFiles.filter(file => {
          const fileName = path.parse(file).name.toLowerCase();
          const searchName = originalName.toLowerCase();
          const firstWord = searchName.split(' ')[0];
          const lastWord = searchName.split(' ').pop();
          
          return fileName.includes(firstWord) || 
                 fileName.includes(lastWord) ||
                 searchName.includes(fileName);
        });
        
        if (partialMatches.length > 0) {
          console.log(`     🔍 Similar files found:`, partialMatches);
        }
      }
    });
    
    console.log('\n' + '=' .repeat(50));
    console.log(`📊 FINAL RESULT: ${matchCount}/${domarData.length} domare matched with images`);
    console.log(`📁 Total image files: ${imageFiles.length}`);
    console.log(`📋 Total CSV records: ${domarData.length}`);
    
    if (matchCount === 0 && imageFiles.length > 0) {
      console.log('\n💡 TROUBLESHOOTING TIPS:');
      console.log('1. Check if image filenames exactly match names in CSV');
      console.log('2. Example CSV name: "Anna Andersson"');
      console.log('3. Expected image file: "Anna Andersson.jpg" (case sensitive)');
      console.log('4. Alternative: "anna andersson.jpg" or "anna-andersson.jpg"');
    }
    
  } catch (error) {
    console.error('❌ Error syncing images:', error);
  }
}

// API endpoint för att hämta data
app.get('/api/getData', (req, res) => {
  const dataWithImages = domarData
    .filter(person => person.imagePath)
    .map(person => [
      person.name,
      person.phone,
      person.domarnummer,
      person.imagePath
    ]);
  
  console.log(`📡 API call: returning ${dataWithImages.length} domare with images`);
  res.json(dataWithImages);
});

// Debug endpoint för att se all data
app.get('/api/debug', (req, res) => {
  res.json({
    totalRecords: domarData.length,
    recordsWithImages: domarData.filter(p => p.imagePath).length,
    sampleData: domarData.slice(0, 5),
    allData: domarData
  });
});

// Servera uppladdade bilder
app.use('/uploads', express.static('uploads'));

// Huvudsida
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// API för att ladda upp ny bild
app.post('/api/upload', upload.single('image'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  
  console.log(`📤 New image uploaded: ${req.file.filename}`);
  syncLocalImages();
  
  res.json({ 
    message: 'File uploaded successfully',
    filename: req.file.filename,
    path: `/uploads/${req.file.filename}`
  });
});

// Starta server
app.listen(PORT, () => {
  console.log(`🚀 Dalecarlia Cup 2025 - Domarkatalog Server`);
  console.log(`🌐 Server running on http://localhost:${PORT}`);
  console.log(`📁 Upload folder: uploads/`);
  console.log(`📊 Data source: data/manifest.csv`);
  console.log('=' .repeat(50));
  loadDataFromCSV();
});

// Reload data periodically
setInterval(() => {
  console.log('\n🔄 Reloading data...');
  loadDataFromCSV();
}, 15 * 60 * 1000);