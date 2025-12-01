from ..pages._app_pages import render_welcome

def main():
    render_welcome()


if __name__ == "__main__":
    main()

# When Streamlit imports this file as a page, call main() immediately
main()
