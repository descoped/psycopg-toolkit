import re


def update_urls(content, repo_url="https://github.com/descoped/psycopg-toolkit/blob/master"):
    pattern = r'\[([^\]]+)\]\(docs/([^)]+)\)'
    return re.sub(pattern, rf'[\1]({repo_url}/docs/\2)', content)


def main():
    with open('README.md', 'r') as f:
        content = f.read()

    updated_content = update_urls(content)

    with open('docs/readme.md', 'w') as f:
        f.write(updated_content)


if __name__ == "__main__":
    main()
