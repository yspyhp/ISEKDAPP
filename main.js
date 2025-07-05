const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// const isDev = !app.isPackaged; 
// true in dev, false in production
const isDev = false;

let serverProcess = null;

function waitForServer(url, maxAttempts = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    
    const checkServer = () => {
      attempts++;
      const req = http.get(url, (res) => {
        if (res.statusCode === 200) {
          console.log('Server is ready!');
          resolve();
        } else {
          if (attempts >= maxAttempts) {
            reject(new Error(`Server not ready after ${maxAttempts} attempts`));
          } else {
            setTimeout(checkServer, 1000);
          }
        }
      });
      
      req.on('error', () => {
        if (attempts >= maxAttempts) {
          reject(new Error(`Server not ready after ${maxAttempts} attempts`));
        } else {
          setTimeout(checkServer, 1000);
        }
      });
      
      req.setTimeout(5000, () => {
        req.destroy();
        if (attempts >= maxAttempts) {
          reject(new Error(`Server not ready after ${maxAttempts} attempts`));
        } else {
          setTimeout(checkServer, 1000);
        }
      });
    };
    
    checkServer();
  });
}

function startServer() {
  if (isDev) {
    // In development, the dev server should already be running
    console.log('Development mode: assuming dev server is running');
    return waitForServer('http://localhost:3000');
  } else {
    // In production, start the standalone server
    return new Promise((resolve, reject) => {
      console.log('Starting standalone server...');
      let serverPath = path.join(__dirname, '.next', 'standalone', 'server.js');
      // If running from asar, use the unpacked path
      if (serverPath.includes('app.asar')) {
        serverPath = serverPath.replace('app.asar', 'app.asar.unpacked');
      }
      console.log('Server path:', serverPath);
      
      // Use bundled Node.js if available, otherwise fall back to system node
      const nodePath = app.isPackaged 
        ? path.join(process.resourcesPath, 'node')
        : 'node';
      
      serverProcess = spawn(nodePath, [serverPath], {
        stdio: 'pipe',
        env: { ...process.env, PORT: '3000' }
      });

      // Log server output for debugging
      serverProcess.stdout.on('data', (data) => {
        console.log('Server stdout:', data.toString());
      });

      serverProcess.stderr.on('data', (data) => {
        console.error('Server stderr:', data.toString());
      });

      serverProcess.on('error', (err) => {
        console.error('Failed to start server:', err);
        reject(err);
      });

      serverProcess.on('exit', (code) => {
        if (code !== 0) {
          console.error(`Server process exited with code ${code}`);
          reject(new Error(`Server process exited with code ${code}`));
        }
      });

      // Wait for server to be ready
      waitForServer('http://localhost:3000')
        .then(() => {
          console.log('Server started successfully');
          resolve();
        })
        .catch((err) => {
          console.error('Server failed to start:', err);
          if (serverProcess) {
            serverProcess.kill();
          }
          reject(err);
        });
    });
  }
}

function createWindow() {
  console.log('Creating Electron window...');
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load the web application
  console.log('Loading URL: http://localhost:3000');
  win.loadURL('http://localhost:3000');
  
  // Open DevTools in development
  if (isDev) {
    win.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  console.log('Electron app is ready');
  startServer().then(() => {
    createWindow();
  }).catch((err) => {
    console.error('Failed to start server:', err);
    // Show error dialog before quitting
    const { dialog } = require('electron');
    dialog.showErrorBox('Server Error', `Failed to start server: ${err.message}`);
    app.quit();
  });
});

app.on('window-all-closed', () => {
  console.log('All windows closed');
  if (serverProcess) {
    console.log('Killing server process');
    serverProcess.kill();
  }
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  console.log('App quitting');
  if (serverProcess) {
    console.log('Killing server process');
    serverProcess.kill();
  }
});

// Global error handler
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  const { dialog } = require('electron');
  dialog.showErrorBox('Uncaught Exception', error.message);
  app.quit();
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  const { dialog } = require('electron');
  dialog.showErrorBox('Unhandled Rejection', reason.toString());
  app.quit();
});
