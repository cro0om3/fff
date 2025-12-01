import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
from pathlib import Path

# Import helpers from app
from app import create_booking_and_get_amount, create_payment_link, verify_payment, BOOKINGS_FILE

class HelpersSmokeTests(unittest.TestCase):
    def setUp(self):
        # Ensure a clean bookings file for tests
        data_dir = Path(BOOKINGS_FILE).parent
        os.makedirs(data_dir, exist_ok=True)
        if os.path.exists(BOOKINGS_FILE):
            os.remove(BOOKINGS_FILE)

    def test_create_booking_and_get_amount_basic(self):
        form = {"name": "Test User", "phone": "0500000000", "tickets": 2, "notes": "test"}
        order_id, amount = create_booking_and_get_amount(form)
        self.assertTrue(order_id.startswith("SL-"))
        self.assertEqual(amount, 2 * 175)
        # bookings file should exist now
        self.assertTrue(os.path.exists(BOOKINGS_FILE))
        df = pd.read_excel(BOOKINGS_FILE)
        self.assertTrue((df['booking_id'] == order_id).any())

    @patch('app.create_payment_intent')
    def test_create_payment_link_without_ziina(self, mocked_pi):
        # Simulate create_payment_intent returning a structure without redirect_url
        mocked_pi.return_value = {"id": "pi_123", "status": "requires_payment_instrument", "hosted_page_url": "https://checkout.example/123"}
        # Create a booking first
        form = {"name": "Test User", "phone": "0500000000", "tickets": 1}
        order_id, amount = create_booking_and_get_amount(form)
        pid, url = create_payment_link(order_id, amount, "Test User")
        self.assertIsNotNone(pid)
        self.assertIsNotNone(url)
        self.assertIn("https://", url)

    @patch('app.get_payment_intent')
    def test_verify_payment_updates_booking(self, mocked_get_pi):
        # Create booking
        form = {"name": "Test User", "phone": "0500000000", "tickets": 1}
        order_id, amount = create_booking_and_get_amount(form)
        # Simulate a payment intent response
        mocked_get_pi.return_value = {"id": "pi_mock", "status": "completed"}
        # Manually set payment_intent_id in bookings file
        df = pd.read_excel(BOOKINGS_FILE)
        df.loc[df['booking_id'] == order_id, 'payment_intent_id'] = 'pi_mock'
        df.to_excel(BOOKINGS_FILE, index=False)
        status = verify_payment('pi_mock')
        self.assertEqual(status, 'completed')
        df2 = pd.read_excel(BOOKINGS_FILE)
        row = df2[df2['booking_id'] == order_id].iloc[0]
        self.assertEqual(row['status'], 'paid')

if __name__ == '__main__':
    unittest.main()
