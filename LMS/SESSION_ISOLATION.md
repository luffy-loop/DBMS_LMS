# LMS browser session isolation

The frontend stores the JWT and current account metadata in `sessionStorage`, not `localStorage`. A normal new tab opened by entering the deployed URL starts with a separate storage area; each tab retains its own login through refresh, and logout clears only that tab's LMS keys. The API client reads the token from the current tab at request time.

**Important browser limitation:** duplicating an existing tab may clone its initial `sessionStorage` state in some browsers. For reliable simultaneous teacher/student testing, open a fresh tab by entering the URL rather than using Duplicate Tab. If you need strict isolation regardless of how a tab is opened, use separate Chrome profiles. This application does not claim protection against a copied browser session or same-origin XSS.

The backend decodes the JWT and reloads the user's current role from PostgreSQL on each authenticated request. A role change therefore takes effect on the next API request even when a tab still holds an older signed token. Passwords remain server-side hashes and are never returned by user-management APIs.
