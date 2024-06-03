import math
import random
import sys
import time
from collections import namedtuple

from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from bash_color import BashColor
from browser_handler import BrowserHandler
from model import Match


class Kicktipp:
    def __init__(self, args):
        self.args = args

        login_form_selector = "//form[@id='loginFormular']"
        self.LOGIN_USERNAME_SELECTOR = login_form_selector + "//input[@id='kennung']"
        self.LOGIN_PASSWORD_SELECTOR = login_form_selector + "//input[@id='passwort']"
        self.LOGIN_BUTTON_SELECTOR = login_form_selector + "//input[@type='submit']"

        self._init_browser()

    def _init_browser(self):
        self.browser_handler = BrowserHandler(self.args)
        self.browser = self.browser_handler.browser
        self.login()

    def login(self):
        self.browser.get("https://www.kicktipp.de/info/profil/login")
        time.sleep(1)

        iteration = 0
        while self._user_is_not_logged_in():
            iteration += 1
            try:
                self._insert_login_credentials()
                self._click_login_button()
            except NoSuchElementException as e:
                if iteration > 10:
                    raise e
                time.sleep(iteration * 1)
                continue
            if iteration > 2:
                self._handle_login_unsuccessful()

    def _handle_privacy_notice_if_present(self):
        privacy_notice = self.browser.find_elements(By.ID, "qc-cmp2-container")
        if len(privacy_notice) == 0:
            return
        privacy_accept_button = privacy_notice[0].find_elements(By.CSS_SELECTOR, ".qc-cmp2-summary-buttons button")
        if privacy_accept_button is not None and len(privacy_accept_button) > 1:
            privacy_accept_button[1].click()
            time.sleep(1)

    def _user_is_not_logged_in(self):
        return len(self.browser.find_elements(By.XPATH, self.LOGIN_BUTTON_SELECTOR)) > 0 \
               and len(self.browser.find_elements(By.XPATH, self.LOGIN_USERNAME_SELECTOR)) > 0 \
               and len(self.browser.find_elements(By.XPATH, self.LOGIN_PASSWORD_SELECTOR)) > 0

    def _insert_login_credentials(self):
        login_field_user = self.browser.find_element(By.XPATH, self.LOGIN_USERNAME_SELECTOR)
        login_field_user.clear()
        login_field_user.send_keys(self.args.username)
        login_field_password = self.browser.find_element(By.XPATH, self.LOGIN_PASSWORD_SELECTOR)
        login_field_password.clear()
        login_field_password.send_keys(self.args.password)

    def _click_login_button(self):
        login_button = self.browser.find_element(By.XPATH, self.LOGIN_BUTTON_SELECTOR)
        login_button.click()
        time.sleep(2)  # wait for page to load

    def _handle_login_unsuccessful(self):
        time.sleep(1)
        if self._user_is_not_logged_in():
            sys.stderr.write("Login to Kicktipp failed.")
            sys.stdout.flush()
            self.browser_handler.kill()
            sys.exit(1)

    def handle_matchday(self, community: str, matchday: int):
        self.go_to_matchday(community, matchday)
        matches = self.retrieve_matches_and_betting_odds()

        self.fill_tips(matches)

        if self.args and (self.args.dryrun or (self.args.verbose and self.args.verbose >= 1)):
            tail = '#' * 75
            print(f"{BashColor.BOLD}### MATCHDAY {matchday: >2} {tail}{BashColor.END}")
            for match in matches:
                if match.odds_home is not None and match.odds_draw is not None and match.odds_guest is not None:
                    self.print_match_with_betting_odds(match)
                elif match.tip_home is not None and match.tip_guest is not None:
                    self.print_match_without_betting_odds(match)
                else:
                    self.print_match_where_no_tips_were_calculated(match)
            print()

        if self.args and not self.args.dryrun:
            self.enter_tips(matches)

    def print_match_with_betting_odds(self, match):
        odds_home_marker, odds_draw_marker, odds_guest_marker = self._define_markers(match)
        print(f"{match.home_team: >15} - {match.guest_team: <15}\t"
              f"{odds_home_marker}{match.odds_home: 7.2f}{BashColor.END} "
              f"{odds_draw_marker}{match.odds_draw: 7.2f}{BashColor.END} "
              f"{odds_guest_marker}{match.odds_guest: 7.2f}{BashColor.END}\t\t"
              f"{BashColor.BLUE}[{match.tip_home: >2} :{match.tip_guest: >2} ]{BashColor.END}")

    @staticmethod
    def print_match_without_betting_odds(match):
        print(f"{match.home_team: >15} - {match.guest_team: <15}\t"
              f"{BashColor.BLUE}[{match.tip_home: >2} :{match.tip_guest: >2} ]{BashColor.END}")

    @staticmethod
    def print_match_where_no_tips_were_calculated(match):
        print(f"{match.home_team: >15} - {match.guest_team: <15}\t"
              f"{BashColor.VIOLET}Could not calculate prediction. Maybe no betting odds were present?{BashColor.END}")

    def fill_tips(self, matches):
        if self.args and self.args.random:
            self.create_random_tips(matches)
        elif self.args and self.args.anti:
            self.create_tips_by_favoring_the_underdog(matches)
        elif self.args and self.args.static:
            self.create_static_tips(matches)
        else:
            self.calculate_tips_by_betting_odds(matches)

    @staticmethod
    def _define_markers(match):
        odds_home_marker = BashColor.YELLOW
        odds_draw_marker = BashColor.YELLOW
        odds_guest_marker = BashColor.YELLOW
        if match.odds_home == min(match.odds_home, match.odds_draw, match.odds_guest):
            odds_home_marker = BashColor.GREEN
        elif match.odds_home == max(match.odds_home, match.odds_draw, match.odds_guest):
            odds_home_marker = BashColor.RED
        if match.odds_draw == min(match.odds_home, match.odds_draw, match.odds_guest):
            odds_draw_marker = BashColor.GREEN
        elif match.odds_draw == max(match.odds_home, match.odds_draw, match.odds_guest):
            odds_draw_marker = BashColor.RED
        if match.odds_guest == min(match.odds_home, match.odds_draw, match.odds_guest):
            odds_guest_marker = BashColor.GREEN
        elif match.odds_guest == max(match.odds_home, match.odds_draw, match.odds_guest):
            odds_guest_marker = BashColor.RED
        return odds_home_marker, odds_draw_marker, odds_guest_marker

    def go_to_matchday(self, community: str, matchday: int):
        self.browser.get(f"https://www.kicktipp.de/{community}/tippabgabe?&spieltagIndex={matchday}")
        time.sleep(2)
        self._handle_privacy_notice_if_present()

    def retrieve_matches_and_betting_odds(self):
        matchday_page = BeautifulSoup(self.browser.page_source, 'html.parser')
        match_rows = matchday_page.find('table', id='tippabgabeSpiele').find_all('tr', class_='datarow')

        matches: list[Match] = []

        for match_row in match_rows[1:]:  # ignore table header row
            match = Match(
                home_team=match_row.find('td', class_='col1').get_text(),
                guest_team=match_row.find('td', class_='col2').get_text(),
            )
            betting_odds_columns = match_row.find_all('a', class_='wettquote-link')
            if len(betting_odds_columns) > 0:
                try:
                    betting_odds = betting_odds_columns[0].get_text().replace('Quote: ', '').split('/')
                    match.odds_home = float(betting_odds[0].replace(',', '.'))
                    match.odds_draw = float(betting_odds[1].replace(',', '.'))
                    match.odds_guest = float(betting_odds[2].replace(',', '.'))
                except ValueError:
                    pass
            matches.append(match)

        return matches

    @staticmethod
    def calculate_tips_by_betting_odds(matches: list[Match]):
        for match in matches:
            if match.odds_home is not None and match.odds_guest is not None:
                match.tip_home = max(round(math.log((match.odds_guest - 1), 1.75)), 0)
                match.tip_guest = max(round(math.log((match.odds_home - 1), 1.75)), 0)

    @staticmethod
    def create_tips_by_favoring_the_underdog(matches: list[Match]):
        for match in matches:
            if match.odds_home is not None and match.odds_guest is not None:
                if match.odds_home < match.odds_guest:
                    match.tip_home = 0
                    match.tip_guest = 1
                else:
                    match.tip_home = 1
                    match.tip_guest = 0

    @staticmethod
    def create_random_tips(matches: list[Match]):
        for match in matches:
            match.tip_home = random.randint(0, 4)
            match.tip_guest = random.randint(0, 4)

    def create_static_tips(self, matches: list[Match]):
        for match in matches:
            match.tip_home, match.tip_guest = self.args.static.split(':')

    def enter_tips(self, matches: list[Match]):
        for i in range(len(matches)):
            match = matches[i]
            if match.tip_home is not None and match.tip_guest is not None:
                match_row = self.browser.find_element(By.ID, 'tippabgabeSpiele').find_elements(By.CSS_SELECTOR, '.datarow')[1:][i]
                input_fields = match_row.find_elements(By.TAG_NAME, 'input')
                if len(input_fields) == 0:
                    print(f"{BashColor.BOLD}{BashColor.VIOLET} └──> WARN: {BashColor.END} "
                          f"could not enter tip for game {BashColor.BOLD}{str(i+1)}{BashColor.END} "
                          "- no input fields present.")
                    continue
                input_fields[1].clear()
                input_fields[1].send_keys(match.tip_home)
                input_fields[2].clear()
                input_fields[2].send_keys(match.tip_guest)

        submit_tips_button = self.browser.find_element(By.XPATH, "//form[@id='tippabgabeForm']//input[@type='submit']")
        self.browser.execute_script("arguments[0].scrollIntoView();", submit_tips_button)
        submit_tips_button.click()
