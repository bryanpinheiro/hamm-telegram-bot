import structlog
import logging
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

class Logger:
    _configured = False
    _log_server_started = False

    @classmethod
    def configure(cls, json_output: bool = True, log_level: int = logging.INFO, log_file: str = None):
        if cls._configured:
            return

        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if log_file:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # File processor for writing to file
            def add_file(logger, method_name, event_dict):
                with open(log_file, 'a') as f:
                    f.write(json.dumps(event_dict) + '\n')
                return event_dict

            processors.append(add_file)

        processors.append(
            structlog.processors.JSONRenderer() if json_output
            else structlog.dev.ConsoleRenderer()
        )

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        cls._configured = True

    @classmethod
    def get_logger(cls, name: str = None):
        if not cls._configured:
            cls.configure()
        return structlog.get_logger(name)

    @classmethod
    def start_log_server(cls, log_file: str, port: int = 8001):
        if cls._log_server_started:
            return

        class LogHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.log_file_path = log_file
                super().__init__(*args, **kwargs)

            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()

                    logs_html = ""
                    if os.path.exists(self.log_file_path):
                        with open(self.log_file_path, 'r') as f:
                            lines = f.readlines()
                            # Reverse to show most recent logs first
                            for line in reversed(lines):
                                line = line.strip()
                                if line:
                                    try:
                                        import json
                                        log_data = json.loads(line)
                                        timestamp = log_data.get('timestamp', 'N/A')
                                        level = log_data.get('level', 'info').upper()
                                        event = log_data.get('event', '')
                                        user_id = log_data.get('user_id', '')

                                        # Color coding by level
                                        level_color = '#4ec9b0'  # cyan for info
                                        if level == 'ERROR':
                                            level_color = '#f48771'  # red
                                        elif level == 'WARNING':
                                            level_color = '#dcdcaa'  # yellow

                                        # Format additional fields
                                        extra_fields = []
                                        for key, value in log_data.items():
                                            if key not in ['timestamp', 'level', 'event']:
                                                extra_fields.append(f'<span class="field">{key}</span>: <span class="value">{value}</span>')

                                        extra_html = ' | '.join(extra_fields) if extra_fields else ''

                                        logs_html += f"""
                                        <div class="log-entry">
                                            <span class="timestamp">{timestamp}</span>
                                            <span class="level" style="color: {level_color}">[{level}]</span>
                                            <span class="event">{event}</span>
                                            {f'<span class="extra"> | {extra_html}</span>' if extra_html else ''}
                                        </div>
                                        """
                                    except json.JSONDecodeError:
                                        logs_html += f'<div class="log-entry">{line}</div>'

                    html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Bot Logs</title>
                        <meta http-equiv="refresh" content="5">
                        <style>
                            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1e1e1e; color: #d4d4d4; padding: 20px; margin: 0; }}
                            h2 {{ margin-top: 0; color: #4ec9b0; }}
                            .log-entry {{ margin: 8px 0; padding: 12px; background: #2d2d2d; border-radius: 6px; border-left: 3px solid #4ec9b0; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; }}
                            .timestamp {{ color: #858585; margin-right: 10px; }}
                            .level {{ font-weight: bold; margin-right: 10px; }}
                            .event {{ color: #dcdcaa; }}
                            .field {{ color: #9cdcfe; }}
                            .value {{ color: #ce9178; }}
                            .extra {{ color: #808080; margin-left: 10px; }}
                            .log-entry:hover {{ background: #383838; }}
                        </style>
                    </head>
                    <body>
                        <h2>Bot Logs <small style="font-size: 14px; color: #858585; font-weight: normal;">(auto-refresh every 5 seconds)</small></h2>
                        <div id="logs">
                            {logs_html}
                        </div>
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not found')

            def log_message(self, format, *args):
                pass  # Suppress HTTP server logs

        def run_server():
            server = HTTPServer(('127.0.0.1', port), LogHandler)
            server.serve_forever()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        cls._log_server_started = True
        return port