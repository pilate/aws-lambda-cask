"""
Basic implementation of PEP-3333 that works with AWS Lambda payload formats.
"""

import base64
import importlib.metadata
import io
import sys
import urllib.parse


__version__ = importlib.metadata.version("aws-lambda-cask")


class StartResponse:
    """https://peps.python.org/pep-3333/#the-start-response-callable"""

    def __init__(self):
        self.status = 500
        self.headers = []
        self.buffer = io.BytesIO()

    def __call__(self, status, headers, exc_info=None):
        self.status = int(status.split()[0])
        self.headers = dict(headers)
        return self.buffer.write

    def response(self, output):
        """
        Create the AWS Lambda response payload from self.buffer + output.
        Always use a base64Encoded body to simplify handling.
        """
        for chunk in output:
            self.buffer.write(chunk)

        self.buffer.seek(0)
        body_raw = self.buffer.read()

        return {
            "statusCode": self.status,
            "headers": self.headers,
            "body": base64.b64encode(body_raw).decode("ascii"),
            "isBase64Encoded": True,
        }


def create_environ(event, context):
    """https://peps.python.org/pep-3333/#environ-variables"""

    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body)
    else:
        body = event.get("body", "").encode("utf-8")

    environ = {
        "SCRIPT_NAME": context.function_name,
        "wsgi.version": (1, 0),
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
        "lambda_wsgi.event": event,
        "lambda_wsgi.context": context,
    }

    for header_key, header_value in event["headers"].items():
        header_key = header_key.upper().replace("-", "_")

        if header_key == "CONTENT_TYPE":
            environ["CONTENT_TYPE"] = header_value
        elif header_key == "CONTENT_LENGTH":
            environ["CONTENT_LENGTH"] = header_value
        elif header_key == "HOST":
            environ["SERVER_NAME"] = header_value
        elif header_key == "X_FORWARDED_FOR":
            environ["REMOTE_ADDR"] = header_value.split(", ")[0]
        elif header_key == "X_FORWARDED_PROTO":
            environ["wsgi.url_scheme"] = header_value
        elif header_key == "X_FORWARDED_PORT":
            environ["SERVER_PORT"] = header_value

        environ[f"HTTP_{header_key}"] = header_value

    request_context = event["requestContext"]

    event_version = event["version"]
    if event_version == "1.0":
        environ.update(
            {
                "REQUEST_METHOD": event["httpMethod"],
                "PATH_INFO": urllib.parse.unquote(event["path"]),
                "QUERY_STRING": urllib.parse.urlencode(
                    event.get("queryStringParameters", {})
                ),
                "SERVER_NAME": request_context.get("domainName"),
                "SERVER_PROTOCOL": request_context["protocol"],
            }
        )
    elif event_version == "2.0":
        http_context = request_context["http"]

        environ.update(
            {
                "REQUEST_METHOD": http_context["method"],
                "PATH_INFO": urllib.parse.unquote(event["rawPath"]),
                "QUERY_STRING": event["rawQueryString"],
                "SERVER_NAME": request_context.get("domainName"),
                "SERVER_PROTOCOL": http_context["protocol"],
            }
        )

    else:
        raise ValueError(f"Unknown lambda payload version: {event_version}")

    return environ


def handle(app, event, context):
    """
    Converts an AWS Lambda event payload and context into the WSGI `environ` format.
    Passes the `environ` and a start_response callable to the WSGI app.
    Converts app response into the AWS Lambda response payload format.

    https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
    """
    start_response = StartResponse()
    output = app(create_environ(event, context), start_response)
    return start_response.response(output)
