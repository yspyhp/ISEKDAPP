# ISEKDAPP

## Development

1. **Install dependencies**
   ```bash
   npm install
   npm install --save-dev electron
   npm install --save-dev electron-builder
   ```

2. **Start in development mode (Next.js + Electron)**
   ```bash
   npm run dev
   # In another terminal:
   npm run electron
   ```

---

## Production Build (Electron App)

1. **Build the Next.js app**
   ```bash
   npm run build
   ```

2. **Copy static assets for standalone server**
   ```bash
   cp -r .next/static .next/standalone/.next/static
   cp -r node_modules .next/standalone/
   ```

3. **Run Electron app in production**
   ```bash
   npm run electron
   ```

---

## Packaging for macOS and Windows

1. **Install electron-builder**

   ```bash
   npm install --save-dev electron-builder
   ```


2. **Build the installer**
   ```bash
   npm run build
   npm run dist
   ```
   - For Windows on macOS, install Wine and run:
     ```bash
     brew install --cask --no-quarantine wine-stable
     npm run dist -- --win
     ```

3. **Find your installers in the `dist/` directory.**

---

## Notes
- Always copy `.next/static` after building for production.
- Customize `build` options in `package.json` as needed (icons, signing, etc).
- See [electron-builder docs](https://www.electron.build/) for advanced options.
