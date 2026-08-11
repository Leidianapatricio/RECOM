from django.test import TestCase
from django.urls import reverse


class HomePageTest(TestCase):

    def test_home_retorna_status_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        

class LoginPageTest(TestCase):

    def test_login_retorna_status_200(self):
        response = self.client.get(reverse("core:login"))
        self.assertEqual(response.status_code, 200)