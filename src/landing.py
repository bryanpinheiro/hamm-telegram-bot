BOT_USERNAME = "hamm_assets_bot"


def render() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hamm</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 24px;
        }}
        .card {{
            background: #2d2d2d;
            border-radius: 12px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
        }}
        h1 {{ margin: 0 0 8px; color: #4ec9b0; font-size: 32px; }}
        p {{ margin: 0 0 28px; color: #9d9d9d; line-height: 1.5; }}
        .cta {{
            display: inline-block;
            padding: 14px 28px;
            border-radius: 8px;
            background: #229ed9;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
        }}
        .cta:hover {{ background: #1b87ba; }}
        .handle {{ display: block; margin-top: 20px; color: #6d6d6d; font-size: 14px; }}
    </style>
</head>
<body>
    <main class="card">
        <h1>Hamm</h1>
        <p>Track the money you receive and the money you spend, straight from Telegram.</p>
        <a class="cta" href="https://t.me/{BOT_USERNAME}">Open in Telegram</a>
        <span class="handle">@{BOT_USERNAME}</span>
    </main>
</body>
</html>
"""
