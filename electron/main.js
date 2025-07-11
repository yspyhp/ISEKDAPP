const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

let mainWindow;
let pythonProcess;

// Start Python backend service
function startPythonBackend() {
  const isDevMode = isDev;
  
  if (isDevMode) {
    // Development mode: run Python script directly
    console.log('Starting Python backend in development mode...');
    pythonProcess = spawn('python', ['../pybackend/app.py'], {
      stdio: 'inherit',
      cwd: path.join(__dirname, '..', 'pybackend')
    });
  } else {
    // Production mode: run packaged executable
    console.log('Starting Python backend in production mode...');
    const pythonExecutable = process.platform === 'win32' ? 'pyserver.exe' : 'pyserver';
    const pythonPath = path.join(process.resourcesPath, pythonExecutable);
    
    pythonProcess = spawn(pythonPath, [], {
      stdio: 'inherit'
    });
  }

  pythonProcess.on('error', (error) => {
    console.error('Failed to start Python backend:', error);
  });

  pythonProcess.on('exit', (code) => {
    console.log(`Python backend exited with code ${code}`);
  });

  return pythonProcess;
}

// Create main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
    titleBarStyle: 'default',
    show: false
  });

  // Load application
  const startUrl = isDev 
    ? 'http://localhost:3000' 
    : `file://${path.join(__dirname, 'dist', 'index.html')}`;
  
  mainWindow.loadURL(startUrl);

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    if (isDev) {
      mainWindow.webContents.openDevTools();
    }
  });

  // Window close event
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App ready
app.whenReady().then(() => {
  // Start Python backend
  startPythonBackend();
  
  // Create main window
  createWindow();

  // macOS app activate event
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// 所有窗口关闭时退出应用
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 应用退出前清理 Python 进程
app.on('before-quit', () => {
  if (pythonProcess) {
    console.log('Terminating Python backend...');
    pythonProcess.kill();
  }
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
}); 