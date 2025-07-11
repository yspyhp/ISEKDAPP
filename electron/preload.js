const { contextBridge, ipcRenderer } = require('electron');

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取应用版本
  getVersion: () => process.versions.electron,
  
  // 获取平台信息
  getPlatform: () => process.platform,
  
  // 检查是否为开发模式
  isDev: () => process.env.NODE_ENV === 'development',
  
  // 窗口操作
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  
  // 获取窗口状态
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  
  // 监听窗口状态变化
  onWindowStateChange: (callback) => {
    ipcRenderer.on('window-state-changed', callback);
  }
}); 