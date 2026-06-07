import time
import base64
import urllib.parse
import re
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext, Browser

BASE_URL = 'https://www.swiggy.com'

class FoodOrderingAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.action_log = []
        self.is_logged_in = False
        self._playwright = None

    def log(self, action: str, target: str, result: str):
        entry = {"action": action, "target": target, "result": result, "timestamp": datetime.utcnow()}
        self.action_log.append(entry)
        print(f"[Agent {self.session_id}] {action} | {target} | {result}")
        return entry

    async def init(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ]
        )
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport=None,
            locale='en-IN',
            timezone_id='Asia/Kolkata',
        )
        self.page = await self.context.new_page()

        # Remove automation flags
        await self.page.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
        """)

        self.log('init', 'browser', 'success')

    # ─────────────────────────────────────────────────────────────────────────
    # LOGIN FLOW
    # ─────────────────────────────────────────────────────────────────────────

    async def enter_phone(self, phone: str) -> dict:
        try:
            self.log('login', 'navigating to swiggy', 'start')

            # Step 1: Load Swiggy homepage
            await self.page.goto(BASE_URL, wait_until='domcontentloaded', timeout=40000)
            await self.page.wait_for_timeout(3000)

            # Step 2: Take screenshot
            screenshot = await self.take_screenshot()

            # Step 3: Click "Sign In"
            sign_in_clicked = await self._click_sign_in()
            self.log('login', 'sign in button', 'clicked' if sign_in_clicked else 'not found, trying /login')

            if not sign_in_clicked:
                await self.page.goto(f"{BASE_URL}/login", wait_until='domcontentloaded', timeout=20000)
                await self.page.wait_for_timeout(2000)

            # Step 4: Wait for phone input
            self.log('login', 'waiting for phone input', 'start')
            phone_input = await self._wait_for_phone_input()

            if not phone_input:
                screenshot = await self.take_screenshot()
                body_text = await self.page.evaluate("document.body.innerText.substring(0, 500)")
                self.log('login', 'phone input', f"NOT FOUND. Page text: {body_text}")
                return {"success": False, "error": "Phone input not found on Swiggy.", "screenshot": screenshot}

            # Step 5: Type phone number
            await phone_input.click(click_count=3)
            await phone_input.fill('')
            await self.page.wait_for_timeout(300)
            await phone_input.type(phone, delay=100)
            await self.page.wait_for_timeout(600)

            self.log('login', 'phone entered', phone)
            screenshot = await self.take_screenshot()

            # Step 6: Click submit
            submitted = await self._click_continue_button()
            self.log('login', 'continue button', 'clicked' if submitted else 'not found, trying Enter key')

            if not submitted:
                await phone_input.press('Enter')

            await self.page.wait_for_timeout(3000)
            screenshot = await self.take_screenshot()

            return {"success": True, "screenshot": screenshot}

        except Exception as err:
            self.log('enter_phone', 'error', str(err))
            screenshot = await self.take_screenshot()
            return {"success": False, "error": str(err), "screenshot": screenshot}

    async def _click_sign_in(self) -> bool:
        selectors = [
            'a:has-text("Sign in")', 'a:has-text("Sign In")',
            'button:has-text("Sign in")', 'button:has-text("Sign In")',
            '[class*="LoginSignupBtn"]', '[class*="login-signup"]',
            '[class*="signIn"]', '[class*="SignIn"]',
            '[data-testid*="login"]', '[data-testid*="signin"]',
            'a[href*="login"]', 'a[href*="signin"]',
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await self.page.wait_for_timeout(2000)
                    return True
            except:
                continue
        return False

    async def _wait_for_phone_input(self, timeout=12000):
        selectors = [
            'input[type="tel"]', 'input[name="mobile"]', 'input[name="phone"]',
            'input[autocomplete="tel"]', 'input[placeholder*="mobile" i]',
            'input[placeholder*="phone" i]', 'input[placeholder*="number" i]',
            'input[placeholder*="Enter" i]', '[class*="PhoneInput"] input',
            '[class*="phoneInput"] input', '[class*="mobileInput"] input',
            '[class*="MobileInput"] input', '[class*="LoginInput"] input',
            '[class*="loginInput"] input', 'input[maxlength="10"]',
            '[class*="modal"] input', '[class*="Modal"] input',
            '[class*="popup"] input', '[class*="Popup"] input',
            'input[type="number"]', 'input[type="text"]',
        ]
        deadline = time.time() + (timeout / 1000)
        while time.time() < deadline:
            for sel in selectors:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible(timeout=500):
                        self.log('_wait_for_phone_input', sel, 'FOUND')
                        return el
                except:
                    continue
            await self.page.wait_for_timeout(500)
        return None

    async def _click_continue_button(self) -> bool:
        selectors = [
            'button:has-text("Continue")', 'button:has-text("continue")',
            'button:has-text("GET OTP")', 'button:has-text("Get OTP")',
            'button:has-text("Send OTP")', 'button:has-text("Login")',
            'button:has-text("Next")', 'button[type="submit"]',
            '[class*="ContinueBtn"]', '[class*="continueBtn"]',
            '[class*="SubmitBtn"]', '[class*="submitBtn"]',
            '[class*="LoginBtn"]', '[class*="loginBtn"]',
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    return True
            except:
                continue
        return False

    async def enter_otp(self, otp: str) -> dict:
        try:
            await self.page.wait_for_timeout(1000)
            screenshot = await self.take_screenshot()

            single_selectors = [
                'input[type="tel"][maxlength="6"]', 'input[type="number"][maxlength="6"]',
                'input[placeholder*="OTP" i]', 'input[placeholder*="otp" i]',
                'input[name="otp"]', '[class*="OtpInput"] input', '[class*="otpInput"] input',
            ]

            filled_single = False
            for sel in single_selectors:
                try:
                    inp = self.page.locator(sel).first
                    if await inp.is_visible(timeout=2000):
                        await inp.click(click_count=3)
                        await inp.fill(otp)
                        filled_single = True
                        self.log('enter_otp', 'single input', 'filled')
                        break
                except:
                    continue

            if not filled_single:
                digit_boxes = await self.page.query_selector_all('input[maxlength="1"]')
                if len(digit_boxes) >= 4:
                    for i in range(min(len(digit_boxes), len(otp))):
                        await digit_boxes[i].click()
                        await digit_boxes[i].fill(otp[i])
                        await self.page.wait_for_timeout(120)
                    filled_single = True
                    self.log('enter_otp', f"{len(digit_boxes)} digit boxes", 'filled')

            if not filled_single:
                screenshot = await self.take_screenshot()
                return {"success": False, "error": "OTP input not found.", "screenshot": screenshot}

            await self.page.wait_for_timeout(800)

            for sel in ['button:has-text("Verify")', 'button:has-text("Submit")', 'button:has-text("Continue")', 'button[type="submit"]']:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=1500):
                        await btn.click()
                        break
                except:
                    continue

            await self.page.wait_for_timeout(4000)

            logged_in = await self._check_login_status()
            screenshot = await self.take_screenshot()

            if logged_in:
                self.is_logged_in = True
                self.log('enter_otp', 'login', 'SUCCESS')
                return {"success": True, "screenshot": screenshot}

            return {"success": False, "error": "OTP incorrect or expired.", "screenshot": screenshot}

        except Exception as err:
            screenshot = await self.take_screenshot()
            return {"success": False, "error": str(err), "screenshot": screenshot}

    async def _check_login_status(self) -> bool:
        try:
            url = self.page.url
            if '/login' in url or '/otp' in url:
                return False

            selectors = [
                '[class*="userProfile"]', '[class*="UserProfile"]',
                '[class*="profileIcon"]', '[aria-label*="account" i]',
                'img[alt*="profile" i]', '[class*="avatar"]',
                '[data-testid*="profile"]',
            ]
            for sel in selectors:
                if await self.page.query_selector(sel):
                    return True
            
            title = await self.page.title()
            if 'swiggy' in title.lower() and 'login' not in title.lower():
                return True
            return False
        except:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH FLOW
    # ─────────────────────────────────────────────────────────────────────────

    async def search_food(self, query: str) -> dict:
        try:
            self.log('search', query, 'start')

            url = f"{BASE_URL}/search?query={urllib.parse.quote(query)}"
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(3500)

            try:
                search_bar = self.page.locator('input[placeholder*="Search" i], [class*="SearchBar"] input').first
                if await search_bar.is_visible(timeout=2000):
                    await search_bar.click()
                    await search_bar.fill('')
                    await search_bar.type(query, delay=80)
                    await self.page.wait_for_timeout(2000)
            except:
                pass

            js_code = """
                () => {
                    const items = [];
                    const cardSelectors = [
                        '[data-testid="restaurant-item"]', '[class*="RestaurantCard"]',
                        '[class*="restaurantCard"]', '[class*="Restaurant_"] > a',
                        'a[href*="/city/"]', 'a[href*="restaurant"]'
                    ];

                    for (const sel of cardSelectors) {
                        const cards = document.querySelectorAll(sel);
                        if (cards.length > 0) {
                            cards.forEach(card => {
                                const name = card.querySelector('[class*="name"],[class*="Name"],h3,h4,[class*="title"]')?.textContent?.trim();
                                const cuisine = card.querySelector('[class*="cuisines"],[class*="Cuisines"],[class*="subtext"]')?.textContent?.trim();
                                const rating = card.querySelector('[class*="rating"],[class*="Rating"],[class*="star"]')?.textContent?.trim();
                                const deliveryTime = card.querySelector('[class*="time"],[class*="Time"],[class*="delivery"]')?.textContent?.trim();
                                const costForTwo = card.querySelector('[class*="cost"],[class*="Cost"],[class*="price"]')?.textContent?.trim();
                                const imgEl = card.querySelector('img');
                                const img = imgEl ? imgEl.src : null;
                                const anchor = card.tagName === 'A' ? card : (card.closest('a') || card.querySelector('a'));
                                const href = anchor ? anchor.href : null;
                                if (name) items.push({ type: 'restaurant', name, cuisine, rating, deliveryTime, costForTwo, img, url: href });
                            });
                            break;
                        }
                    }

                    if (items.length === 0) {
                        document.querySelectorAll('[data-testid="normal-dish-item"],[class*="DishCard"],[class*="MenuItem"]').forEach(dish => {
                            const name = dish.querySelector('[class*="name"],h4')?.textContent?.trim();
                            const price = dish.querySelector('[class*="price"]')?.textContent?.trim();
                            const restaurant = dish.querySelector('[class*="restaurant"],[class*="subText"]')?.textContent?.trim();
                            const img = dish.querySelector('img')?.src;
                            if (name) items.push({ type: 'dish', name, price, restaurant, img });
                        });
                    }

                    return items.slice(0, 8);
                }
            """
            results = await self.page.evaluate(js_code)

            self.log('search', query, f"{len(results)} results")
            screenshot = await self.take_screenshot()
            return {"success": True, "results": results, "query": query, "screenshot": screenshot}

        except Exception as err:
            self.log('search', query, f"ERROR: {str(err)}")
            return {"success": False, "error": str(err), "results": []}

    async def navigate_to_restaurant(self, url: str) -> dict:
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(3000)
            self.log('navigate', url, 'success')
            menu_items = await self._scrape_menu_items()
            screenshot = await self.take_screenshot()
            return {"success": True, "menuItems": menu_items, "screenshot": screenshot}
        except Exception as err:
            return {"success": False, "error": str(err)}

    async def _scrape_menu_items(self) -> list:
        try:
            await self.page.wait_for_timeout(2000)
            js_code = """
                () => {
                    const items = [];
                    const selectors = ['[data-testid="normal-dish-item"]', '[class*="MenuItem"]', '[class*="menuItem"]', '[class*="DishInfo"]'];
                    for (const sel of selectors) {
                        const els = document.querySelectorAll(sel);
                        if (els.length > 0) {
                            els.forEach(el => {
                                const nameNode = el.querySelector('[data-testid="item-name"]') || el.querySelector('[class*="name"]') || el.querySelector('h4');
                                const name = nameNode?.textContent?.trim();
                                const price = el.querySelector('[class*="price"]')?.textContent?.trim();
                                const available = !el.querySelector('[class*="OutOfStock"],[class*="outOfStock"]');
                                const img = el.querySelector('img')?.src;
                                if (name) items.push({ name, price, available, img });
                            });
                            break;
                        }
                    }
                    return items.slice(0, 20);
                }
            """
            return await self.page.evaluate(js_code)
        except:
            return []

    async def add_item_to_cart(self, item_name: str, quantity: int = 1, customizations: list = [], restaurant_name: str = None) -> dict:
        try:
            if restaurant_name:
                rest_selectors = ['[data-testid="restaurant-item"]', '[class*="RestaurantCard"]', 'a[href*="/city/"]', '[class*="Restaurant_"]']
                for r_sel in rest_selectors:
                    try:
                        card = self.page.locator(r_sel, has_text=re.compile(re.escape(restaurant_name), re.IGNORECASE)).first
                        if await card.is_visible(timeout=1500):
                            await card.click()
                            await self.page.wait_for_timeout(3500)
                            break
                    except:
                        continue

            locators = ['[data-testid="normal-dish-item"]', '[class*="MenuItem"]', '[class*="DishInfo"]']
            item_el = None
            for loc in locators:
                try:
                    el = self.page.locator(loc, has_text=re.compile(re.escape(item_name), re.IGNORECASE)).first
                    if await el.is_visible(timeout=3000):
                        item_el = el
                        break
                except:
                    continue

            if not item_el:
                return {"success": False, "error": f'"{item_name}" not found', "outOfStock": False}

            is_oos = await item_el.locator('[class*="OutOfStock"],[class*="outOfStock"]').count() > 0
            if is_oos:
                return {"success": False, "error": f'"{item_name}" is out of stock', "outOfStock": True}

            added = False
            for sel in ['[data-testid="add-to-cart"]', 'button:has-text("ADD")', 'button:has-text("Add")', '[class*="addBtn"]', 'button:has-text("+")']:
                try:
                    btn = item_el.locator(sel).first
                    if await btn.is_visible(timeout=1500):
                        await btn.click(force=True)
                        added = True
                        await self.page.wait_for_timeout(800)
                        break
                except:
                    continue

            if not added:
                try:
                    any_button = item_el.locator('button').first
                    if await any_button.is_visible(timeout=1000):
                        await any_button.click(force=True)
                        added = True
                    else:
                        await item_el.click(force=True)
                        added = True
                    await self.page.wait_for_timeout(800)
                except:
                    pass

            await self._handle_customization_modal(customizations)
            if quantity > 1:
                await self._adjust_quantity(quantity)
                
            screenshot = await self.take_screenshot()
            return {"success": added, "itemName": item_name, "quantity": quantity, "screenshot": screenshot}
            
        except Exception as err:
            return {"success": False, "error": str(err)}

    async def _handle_customization_modal(self, customizations: list = []):
        try:
            await self.page.wait_for_timeout(800)
            modal = await self.page.query_selector('[class*="ItemModal"],[class*="Customisation"],[class*="customisation"]')
            if not modal: return
            
            for c in customizations:
                try:
                    opt = self.page.locator(f'label:has-text("{c}"),[class*="option"]:has-text("{c}")').first
                    if await opt.is_visible(timeout=1000):
                        await opt.click()
                except:
                    continue
                    
            for sel in ['button:has-text("Done")', 'button:has-text("Add Item")', 'button:has-text("Confirm")']:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        break
                except:
                    continue
        except:
            pass

    async def _adjust_quantity(self, target_qty: int):
        for _ in range(1, target_qty):
            for sel in ['[data-testid="increase-count"]', '[class*="increaseCount"]', 'button:has-text("+")']:
                try:
                    btn = self.page.locator(sel).last
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        await self.page.wait_for_timeout(300)
                        break
                except:
                    continue

    async def get_cart_contents(self) -> dict:
        try:
            await self.page.goto(f"{BASE_URL}/cart", wait_until='domcontentloaded', timeout=15000)
            await self.page.wait_for_timeout(1500)
            
            js_code = """
                () => {
                    const items = [];
                    document.querySelectorAll('[class*="CartItem"],[class*="cartItem"]').forEach(el => {
                        const name = (el.querySelector('[class*="name"]') || el.querySelector('h4'))?.textContent?.trim();
                        const qty = el.querySelector('[class*="count"],[class*="quantity"]')?.textContent?.trim() || '1';
                        const price = el.querySelector('[class*="price"]')?.textContent?.trim();
                        if (name) items.push({ name, quantity: parseInt(qty) || 1, price });
                    });
                    const total = document.querySelector('[class*="TotalPayable"],[class*="grandTotal"]')?.textContent?.trim();
                    return { items, total };
                }
            """
            data = await self.page.evaluate(js_code)
            screenshot = await self.take_screenshot()
            return {"success": True, **data, "screenshot": screenshot}
        except Exception as err:
            return {"success": False, "error": str(err), "items": []}

    async def proceed_to_checkout(self) -> dict:
        try:
            for sel in ['button:has-text("Proceed to Pay")', 'button:has-text("Place Order")', '[class*="proceedToPay"]']:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        await self.page.wait_for_timeout(2000)
                        screenshot = await self.take_screenshot()
                        return {"success": True, "screenshot": screenshot}
                except:
                    continue
            return {"success": False, "error": "Checkout button not found"}
        except Exception as err:
            return {"success": False, "error": str(err)}

    async def take_screenshot(self) -> str:
        try:
            buf = await self.page.screenshot(type='png', full_page=False)
            return base64.b64encode(buf).decode('utf-8')
        except:
            return None

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()


# ── Agent pool ────────────────────────────────────────────────────────────────
_agent_pool = {}

def get_agent(sid: str) -> FoodOrderingAgent:
    return _agent_pool.get(sid)

async def create_agent(sid: str) -> FoodOrderingAgent:
    if sid in _agent_pool:
        return _agent_pool[sid]
    agent = FoodOrderingAgent(sid)
    await agent.init()
    _agent_pool[sid] = agent
    return agent

async def destroy_agent(sid: str):
    agent = _agent_pool.get(sid)
    if agent:
        await agent.close()
        del _agent_pool[sid]
