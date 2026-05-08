"""
Notion OAuth Client

A reusable OAuth client for Notion API authentication.
Handles the complete OAuth flow including authorization and token exchange.
"""

import webbrowser
import time
from typing import Dict, Optional, Callable, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread
import requests

from logger import get_logger

logger = get_logger(__name__)


class NotionOAuthClient:
    """
    Handles OAuth authentication flow for Notion API.
    
    This client manages:
    - Authorization URL generation
    - Local callback server for receiving auth codes
    - Token exchange with Notion API
    - Token storage and retrieval
    
    Example:
        ```python
        oauth_client = NotionOAuthClient(
            client_id="your_client_id",
            redirect_uri="http://localhost:8080/oauth/callback"
        )
        
        # Start OAuth flow
        token_data = oauth_client.authorize()
        
        # Use the access token
        access_token = token_data['access_token']
        ```
    """
    
    AUTHORIZATION_URL = "https://api.notion.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.notion.com/v1/oauth/token"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/oauth/callback",
        timeout: int = 300
    ):
        """
        Initialize the OAuth client.
        
        Args:
            client_id: Notion OAuth client ID
            client_secret: Notion OAuth client secret
            redirect_uri: OAuth callback URL (must match Notion integration settings)
            timeout: Maximum time to wait for authorization (seconds)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.timeout = timeout
        
        # Internal state
        self._auth_code: Optional[str] = None
        self._server_should_stop = False
        self._callback_handler = None
    
    def authorize(
        self,
        auto_open_browser: bool = True,
        on_success: Optional[Callable[[Dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete OAuth flow.
        
        This method:
        1. Starts a local callback server
        2. Opens the authorization URL in browser
        3. Waits for the callback with auth code
        4. Exchanges auth code for access token
        5. Returns token data
        
        Args:
            auto_open_browser: Whether to automatically open browser
            on_success: Callback function called with token data on success
            on_error: Callback function called with error message on failure
            
        Returns:
            Dictionary containing token data:
            {
                'access_token': str,
                'workspace_id': str,
                'workspace_name': str,
                'workspace_icon': str,
                'bot_id': str,
                'owner': dict
            }
            
        Raises:
            TimeoutError: If authorization times out
            Exception: If token exchange fails
        """
        try:
            # Reset state
            self._auth_code = None
            self._server_should_stop = False
            
            # Start callback server
            logger.info("Starting local callback server...")
            server_thread = self._start_callback_server()
            
            # Build authorization URL
            auth_url = self._build_auth_url()
            
            # Open browser
            if auto_open_browser:
                logger.info("Opening browser for authorization...")
                webbrowser.open(auth_url)
            else:
                logger.info(f"Please visit this URL to authorize:\n{auth_url}")
            
            logger.info("Waiting for authorization...")
            
            # Wait for callback
            server_thread.join(timeout=self.timeout)
            
            if not self._auth_code:
                error_msg = "Authorization failed or timed out"
                logger.error(error_msg)
                if on_error:
                    on_error(error_msg)
                raise TimeoutError(error_msg)
            
            logger.info("Authorization code received!")
            
            # Exchange code for token
            token_data = self._exchange_code_for_token(self._auth_code)
            
            logger.info("Access token obtained successfully!")
            
            if on_success:
                on_success(token_data)
            
            return token_data
            
        except Exception as e:
            error_msg = f"OAuth flow failed: {e}"
            logger.error(error_msg)
            if on_error:
                on_error(error_msg)
            raise
    
    def _build_auth_url(self) -> str:
        """Build the authorization URL."""
        return (
            f"{self.AUTHORIZATION_URL}?"
            f"client_id={self.client_id}&"
            f"response_type=code&"
            f"owner=user&"
            f"redirect_uri={self.redirect_uri}"
        )
    
    def _start_callback_server(self) -> Thread:
        """Start the local callback server in a background thread."""
        # Parse redirect URI to get host and port
        parsed = urlparse(self.redirect_uri)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 8080
        
        # Create callback handler class with access to this instance
        oauth_client = self
        
        class OAuthCallbackHandler(BaseHTTPRequestHandler):
            """Handle OAuth callback from Notion."""
            
            def log_message(self, format, *args):
                """Suppress default logging."""
                pass
            
            def do_GET(self):
                """Handle GET request from OAuth callback."""
                parsed_url = urlparse(self.path)
                
                if parsed_url.path == parsed.path:
                    query_params = parse_qs(parsed_url.query)
                    
                    if 'code' in query_params:
                        oauth_client._auth_code = query_params['code'][0]
                        
                        # Send success response
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        success_html = """
                        <html>
                        <head><title>OAuth Success</title></head>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h1 style="color: green;">✓ Authorization Successful!</h1>
                            <p>You can close this window and return to the terminal.</p>
                            <script>setTimeout(function(){ window.close(); }, 3000);</script>
                        </body>
                        </html>
                        """
                        self.wfile.write(success_html.encode())
                        
                        oauth_client._server_should_stop = True
                        
                    elif 'error' in query_params:
                        error = query_params['error'][0]
                        
                        # Send error response
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        error_html = f"""
                        <html>
                        <head><title>OAuth Error</title></head>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h1 style="color: red;">✗ Authorization Failed</h1>
                            <p>Error: {error}</p>
                            <p>You can close this window and try again.</p>
                        </body>
                        </html>
                        """
                        self.wfile.write(error_html.encode())
                        
                        oauth_client._server_should_stop = True
                else:
                    self.send_response(404)
                    self.end_headers()
        
        def run_server():
            """Run the HTTP server."""
            server = HTTPServer((host, port), OAuthCallbackHandler)
            logger.info(f"Started local server on {oauth_client.redirect_uri}")
            
            while not oauth_client._server_should_stop:
                server.handle_request()
            
            server.server_close()
            logger.info("Stopped local server")
        
        # Start server in background thread
        server_thread = Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Give server time to start
        time.sleep(1)
        
        return server_thread
    
    def _exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Dictionary containing token data
            
        Raises:
            Exception: If token exchange fails
        """
        logger.info("Exchanging authorization code for access token...")
        
        response = requests.post(
            self.TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri
            },
            headers={
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"Token exchange failed: {response.status_code} - {response.text}"
            )
    
    @staticmethod
    def get_auth_url_manual(
        client_id: str,
        redirect_uri: str = "http://localhost:8080/oauth/callback"
    ) -> str:
        """
        Generate authorization URL without starting OAuth flow.
        
        Useful for manual OAuth flows or testing.
        
        Args:
            client_id: Notion OAuth client ID
            redirect_uri: OAuth callback URL
            
        Returns:
            Authorization URL string
        """
        return (
            f"{NotionOAuthClient.AUTHORIZATION_URL}?"
            f"client_id={client_id}&"
            f"response_type=code&"
            f"owner=user&"
            f"redirect_uri={redirect_uri}"
        )