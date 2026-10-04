/* signed in? (the "si" cookie, set with the session) → the nav shows Account, before the page paints */
if (/(?:^|;\s*)si=1/.test(document.cookie)) document.documentElement.classList.add('si');
/* billing details not set up yet ("sb" cookie) → a dot on Account */
if (/(?:^|;\s*)sb=1/.test(document.cookie)) document.documentElement.classList.add('sb');
/* this account has had a plan, a free trial included ("hp" cookie) → the main button says Buy now, not Try for Free */
if (/(?:^|;\s*)hp=1/.test(document.cookie)) document.documentElement.classList.add('hp');
