# BathChat Frontend Web Page

This folder contains a single-page frontend that calls all backend endpoints currently defined in backend/main.py.

## Files

- index.html: UI with forms for every endpoint
- styles.css: styling
- app.js: API request logic and handlers

## Run

1. Start the backend API.
2. Open index.html in your browser.
3. Set Base URL and X-User-Id in the page.
4. Use the endpoint cards to test routes.

## Endpoints Covered

- POST /auth/register
- POST /auth/login
- GET /auth/me
- POST /profiles/me
- GET /profiles/me
- GET /leaderboard/top-exp
- POST /discovery/match/{candidate_id}
- GET /discovery/matches
- POST /connections/{candidate_id}
- GET /connections
- POST /connections/{connection_user_id}/chat
- GET /connections/{connection_user_id}/chat
- POST /messages/send
- POST /friends/request/{receiver_id}
- POST /friends/request/{request_id}/accept
