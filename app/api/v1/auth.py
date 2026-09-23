from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

# Hardcoded test credentials
TEST_USERNAME = "test"
TEST_PASSWORD = "password"

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Return a simple login page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
    </head>
    <body>
        <h2>Login</h2>
        <form method="post" action="/api/v1/login">
            <div>
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div>
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div>
                <button type="submit">Login</button>
            </div>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Handle login form submission."""
    if username == TEST_USERNAME and password == TEST_PASSWORD:
        # Successful login - redirect to dashboard
        return RedirectResponse(url="/api/v1/dashboard", status_code=status.HTTP_302_FOUND)
    else:
        # Failed login - return login page with error
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login</title>
        </head>
        <body>
            <h2>Login</h2>
            <p style="color: red;">Invalid username or password</p>
            <form method="post" action="/api/v1/login">
                <div>
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div>
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <div>
                    <button type="submit">Login</button>
                </div>
            </form>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=status.HTTP_401_UNAUTHORIZED)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Return a simple dashboard page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
    </head>
    <body>
        <h2>Dashboard</h2>
        <p>Welcome to the dashboard!</p>
        <p>You have successfully logged in.</p>
        <a href="/api/v1/login">Logout</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)