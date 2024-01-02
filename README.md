# aws-lambda-cask
Wrapper to enable usage of Python WSGI frameworks (bottle, django, flask, etc.) within AWS Lambda environments.

Supports v1.0 (API Gateway) and v2.0 (Lambda URL) payload formats.

# Installation
```
$ pip install aws-lambda-cask
```

# Flask example

```python

import flask
import lambda_cask


app = flask.Flask(__name__)


@app.route("/")
def index():
    return "eyy"


def handler(event, context):
    return lambda_cask.handle(app, event, context)

```
