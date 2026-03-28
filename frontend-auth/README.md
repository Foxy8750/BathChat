# BathChat Auth Frontend

Simple static auth UI for BathChat backend, deployable on Firebase Hosting.

## Local Preview

1. Open `public/index.html` directly in your browser, or serve this folder with any static server.
2. Set Backend Base URL to your FastAPI backend URL (for local backend use `http://127.0.0.1:8001`).
3. Test Sign Up and Log In.

## Firebase Hosting Deployment

1. Install Firebase CLI:
   - `npm install -g firebase-tools`
2. Login:
   - `firebase login`
3. Set your Firebase project ID in `.firebaserc`.
4. From this folder, deploy:
   - `firebase deploy --only hosting`

## Backend CORS

Set this on backend so browser calls are allowed from your frontend domain:

- `CORS_ALLOWED_ORIGINS=https://your-project-id.web.app,https://your-project-id.firebaseapp.com,http://127.0.0.1:3000`

You can also include your local origin(s) for development.
