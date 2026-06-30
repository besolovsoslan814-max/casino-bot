# LaunchQuill Landing Page Guide

## Project Overview
LaunchQuill is a single-page React 18 + Vite + Tailwind application that renders a conversion-focused landing page for an AI coding agent targeting SaaS founders. The app lives entirely in `src/App.tsx` where strongly typed configuration objects (benefits, testimonials, stats, features, pricing, FAQs) drive section rendering. The page prioritizes conversion with a hero split layout, scroll sections for value proposition, benefits, walkthrough, social proof, pricing, FAQ, and a waitlist form powered by mock submission logic.

## Development Commands
- Install dependencies: `npm install`
- Start dev server: `npm run dev`
- Build for production: `npm run build`

## Application Structure
`App.tsx` declares TypeScript interfaces for each content group and uses `useMemo` to memoize mock data arrays. Functional substructures (check icon component, form handler) live inline to keep the single-page composition coherent. Tailwind utility classes deliver layout and theming, while new image assets are imported from `src/assets`. The waitlist form validates name and email, simulates submission with `setTimeout`, and surfaces error/success states without backend dependencies.

## Design System Notes
Primary palette uses warm neutrals with deep blue-gray accents (`#F7F5F1`, `#1F2A33`, `#2E3F4A`). Typography relies on Tailwind defaults with uppercase tracking for metadata lines. Section spacing follows 8px multiples and grid-based responsive layouts (single column on mobile, multi-column on ≥1024px). Sticky header, rounded cards, and subtle shadows reinforce the premium business tone. Hero gallery combines three curated assets to show team collaboration and product UI. CTA buttons respect minimum tap targets (≥44px height) and maintain contrast ratios above 4.5:1.

## Assets
New imagery generated via Flux lives in `src/assets/hero-founders.jpeg`, `src/assets/ui-dashboard.jpeg`, and `src/assets/laptop-mock.jpeg`; background texture remains `src/assets/youware-bg.png`. All images are referenced through ES module imports for Vite optimization. Replace or compress assets through the same directory to keep pipeline intact.

## Mock Data and Extensibility
All structured content is isolated inside memoized arrays so founders can later replace mock copy or wire API responses without altering layout logic. The waitlist form is prepared for backend integration by swapping the timeout with a real request. Remove the placeholder video source in the walkthrough section or replace it with an actual asset when available.
