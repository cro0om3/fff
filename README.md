# SNOW LIWA – Booking & Payment App

This is a Streamlit app for **SNOW LIWA**:

- Landing page with background from your PDF.
- Pages:
  - Welcome & Ticket booking
  - Who we are
  - Experience
  - Contact
  - Admin Dashboard
- Payment:
  - Uses **Ziina Payment Intent API**.
  - Creates a payment intent and redirects user to Ziina.
  - After payment, Ziina redirects back to the app with `result` and `pi_id` in the URL.
- Data:
  - Stores bookings in `data/bookings.xlsx`.

## Setup

1. Create a virtual environment (optional).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Put your background image here:

   ```text
   assets/snow_liwa_bg.jpg
   ```

4. Configure Ziina secrets in `.streamlit/secrets.toml`.

Secrets options
----------------

- Copy the example and fill in your real credentials:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit `.streamlit/secrets.toml` and replace placeholders
```

- Alternatively, set environment variables (useful for CI or local shells):

```powershell
$env:ZIINA_ACCESS_TOKEN = "your_token"
$env:ZIINA_APP_BASE_URL = "https://your-app.example.com"
```

- On Streamlit Cloud add the same keys as app secrets under the "Secrets" section.

5. Run the app:

   ```bash
   streamlit run app.py
   ```
