// 🍁 MAPLE n8n Integration Build Configuration
// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

const gulp = require('gulp');
const typescript = require('gulp-typescript');
const sourcemaps = require('gulp-sourcemaps');
const del = require('del');
const path = require('path');
const fs = require('fs');

console.log('🍁 MAPLE n8n Build System');
console.log('Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)');

// TypeScript project
const tsProject = typescript.createProject('tsconfig.json');

// Clean dist directory
gulp.task('clean', () => {
  return del(['dist/**/*']);
});

// Build TypeScript
gulp.task('build:ts', () => {
  return gulp.src(['credentials/**/*.ts', 'nodes/**/*.ts', 'lib/**/*.ts'])
    .pipe(sourcemaps.init())
    .pipe(tsProject())
    .pipe(sourcemaps.write('.'))
    .pipe(gulp.dest('dist'));
});

// Copy assets and static files
gulp.task('copy:assets', () => {
  return gulp.src(['assets/**/*', 'workflows/**/*'], { base: '.' })
    .pipe(gulp.dest('dist'));
});

// Build icons (create placeholder icons for the nodes)
gulp.task('build:icons', (done) => {
  const iconsDir = path.join(__dirname, 'assets');
  
  // Ensure assets directory exists
  if (!fs.existsSync(iconsDir)) {
    fs.mkdirSync(iconsDir, { recursive: true });
  }
  
  // Create simple SVG icons for the nodes
  const icons = [
    {
      name: 'maple.svg',
      content: `<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="60" fill="#ff6b35" rx="8"/>
        <text x="30" y="40" font-family="Arial, sans-serif" font-size="32" font-weight="bold" text-anchor="middle" fill="white">🍁</text>
      </svg>`
    },
    {
      name: 'maple-coord.svg', 
      content: `<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="60" fill="#3498db" rx="8"/>
        <text x="30" y="40" font-family="Arial, sans-serif" font-size="32" font-weight="bold" text-anchor="middle" fill="white">🎼</text>
      </svg>`
    },
    {
      name: 'maple-resources.svg',
      content: `<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="60" fill="#27ae60" rx="8"/>
        <text x="30" y="40" font-family="Arial, sans-serif" font-size="32" font-weight="bold" text-anchor="middle" fill="white">💾</text>
      </svg>`
    }
  ];
  
  icons.forEach(icon => {
    const iconPath = path.join(iconsDir, icon.name);
    fs.writeFileSync(iconPath, icon.content);
    console.log(`✅ Created icon: ${icon.name}`);
  });
  
  done();
});

// Watch for changes during development
gulp.task('watch', () => {
  gulp.watch(['credentials/**/*.ts', 'nodes/**/*.ts', 'lib/**/*.ts'], gulp.series('build:ts'));
  gulp.watch(['assets/**/*'], gulp.series('copy:assets'));
});

// Validate build output
gulp.task('validate', (done) => {
  const requiredFiles = [
    'dist/credentials/MAPLEApi.credentials.js',
    'dist/nodes/MAPLEAgent/MAPLEAgent.node.js',
    'dist/nodes/MAPLECoordinator/MAPLECoordinator.node.js',
    'dist/nodes/MAPLEResourceManager/MAPLEResourceManager.node.js',
    'dist/lib/MAPLEClient.js'
  ];
  
  let allFilesExist = true;
  
  requiredFiles.forEach(file => {
    if (fs.existsSync(file)) {
      console.log(`✅ ${file}`);
    } else {
      console.log(`❌ Missing: ${file}`);
      allFilesExist = false;
    }
  });
  
  if (allFilesExist) {
    console.log('✅ Build validation passed');
  } else {
    console.log('❌ Build validation failed');
    process.exit(1);
  }
  
  done();
});

// Generate package info
gulp.task('package:info', (done) => {
  const packageJson = require('./package.json');
  
  const buildInfo = {
    name: packageJson.name,
    version: packageJson.version,
    description: packageJson.description,
    creator: packageJson.author.name,
    buildDate: new Date().toISOString(),
    nodes: [
      'MAPLEAgent',
      'MAPLECoordinator', 
      'MAPLEResourceManager'
    ],
    credentials: [
      'MAPLEApi'
    ],
    workflows: [
      'ai-research-assistant',
      'content-creation-pipeline',
      'customer-service-bot'
    ]
  };
  
  const buildInfoPath = path.join(__dirname, 'dist', 'build-info.json');
  fs.writeFileSync(buildInfoPath, JSON.stringify(buildInfo, null, 2));
  
  console.log('📦 Package info generated');
  done();
});

// Main build task
gulp.task('build', gulp.series(
  'clean',
  'build:icons',
  'build:ts',
  'copy:assets',
  'package:info',
  'validate'
));

// Development task
gulp.task('dev', gulp.series('build', 'watch'));

// Default task
gulp.task('default', gulp.series('build'));

console.log('🎯 Available tasks:');
console.log('   gulp build     - Full build');
console.log('   gulp dev       - Development mode with watch');
console.log('   gulp clean     - Clean dist directory');
console.log('   gulp validate  - Validate build output');
