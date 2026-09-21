"""Demo application for testing autonomous testing framework.

A simple login/logout web application using FastAPI.
"""
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

app = FastAPI()

# Hardcoded credentials (for demo purposes)
USERNAME = os.getenv("DEMO_APP_USERNAME", "testuser")
PASSWORD = os.getenv("DEMO_APP_PASSWORD", "securepass")

# Simple session management via cookie (in production, use proper sessions)
SESSION_COOKIE_NAME = "demo_session"

# Templates
templates = Jinja2Templates(directory="demo_app/templates")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), response: Response = None):
    if username == USERNAME and password == PASSWORD:
        # Set a simple session cookie
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key=SESSION_COOKIE_NAME, value="authenticated", httponly=True)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(None)):
    if session != "authenticated":
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
