# PLAN-frontend-ui

## Goal
Build a modern, high-information-density React application for the Finance Intelligence Portal with a "Bloomberg Terminal" aesthetic using Tailwind CSS v4, Glassmorphism, and Framer Motion.

## Tasks
- [x] Task 1: Scaffold Vite-based React project in `/frontend` directory.
- [ ] Task 2: Install dependencies including `tailwindcss`, `lucide-react`, `axios`, `framer-motion`, `recharts` (handling EACCES permission fallback using `--force`).
- [ ] Task 3: Setup Tailwind v4 with the CSS-first architecture (`@tailwindcss/vite`).
- [ ] Task 4: Create the `Sidebar.jsx` component representing the Budget Tracker, Ticker Selectors, and Year Sliders.
- [ ] Task 5: Create the `MainChat.jsx` layout for the chat message stream with a glassmorphism effect and Markdown support, including the "Thinking" state logic.
- [ ] Task 6: Create the `SourceDrawer.jsx` component for rendering relevant document chunks upon citation click.
- [ ] Task 7: Complete `App.jsx` and hook up layout integration and Axios API requests to backend (`http://localhost:8000`).

## Done When
- [ ] Vite project starts without errors.
- [ ] Chat layout correctly renders Glassmorphic components.
- [ ] Dark Mode Bloomberg Terminal aesthetic is achieved.
- [ ] Axios connects to local FastAPI.
