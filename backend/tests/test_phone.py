import unittest

from app.services.phone import normalize_indian_phone


class PhoneNormalizationTests(unittest.TestCase):
    def test_spoken_digits(self):
        self.assertEqual(
            normalize_indian_phone("nine eight seven six five four three two one zero"),
            "+919876543210",
        )

    def test_numeric_number_with_country_code(self):
        self.assertEqual(normalize_indian_phone("+91 98765 43210"), "+919876543210")

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            normalize_indian_phone("987654")

    def test_rejects_invalid_first_digit(self):
        with self.assertRaises(ValueError):
            normalize_indian_phone("1234567890")


if __name__ == "__main__":
    unittest.main()
