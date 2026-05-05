from flask import Flask, render_template, request
import anthropic
import os

app = Flask(__name__)


@app.route('/')
def index():
    # Load and display joblist.md
    pass


@app.route('/generate', methods=['POST'])
def generate():
    # Read job URL and role type
    # Load SKILL.md and correct CV base
    # Call Claude API to generate CV and cover letter
    # Return generated documents
    pass


if __name__ == '__main__':
    app.run(debug=True)
