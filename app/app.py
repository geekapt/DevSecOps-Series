from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Secure CI/CD with GitHub OIDC!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

