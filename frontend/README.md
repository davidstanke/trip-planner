# Trip Planner - Frontend Service

A modern, responsive React + Vite web application built with Vanilla CSS and TypeScript. It provides an intuitive, interactive UI for planning road trips, booking hotels, and discovering activities using the Trip Planner Agent backend.

---

## 🚀 Getting Started

Follow these steps to set up and run the frontend service locally.

### Prerequisites

Ensure you have the following installed on your local machine:
- **Node.js** (v18.0.0 or higher recommended)
- **npm** (v9.0.0 or higher recommended) or **yarn** / **pnpm**

---

## 🛠️ Installation & Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   Using npm:
   ```bash
   npm install
   ```
   Or using yarn/pnpm:
   ```bash
   yarn install
   # or
   pnpm install
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the `frontend` root directory (if not already present):
   ```bash
   touch .env
   ```
   Configure the backend connection URL or any other required environment variables inside `.env`:
   ```env
   VITE_API_URL=http://localhost:8000
   ```

---

## 🏃 Running the Local Server

To start the local development server with Hot Module Replacement (HMR) and source maps:

```bash
npm run dev
```

Once started, the application will run locally at:
👉 **[http://localhost:5173](http://localhost:5173)** (or the port specified in your terminal)

---

## 📦 Building for Production

To compile and optimize the frontend for production:

```bash
npm run build
```

This will generate a highly optimized production bundle in the `dist/` directory, ready to be deployed to your favorite hosting service (e.g., Firebase Hosting, Vercel, or Netlify).

### Preview the Production Build

You can preview the compiled production build locally to verify all assets and routes load correctly:

```bash
npm run preview
```

---

## 🔍 Code Quality & Linting

To check the code quality using ESLint:

```bash
npm run lint
```
