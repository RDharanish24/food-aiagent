import time
import base64
import urllib.parse
import re
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth import stealth

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
        # Launching headless=True as requested for execution worker, using stealth
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080',
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-IN',
            timezone_id='Asia/Kolkata',
            permissions=['geolocation'],
            color_scheme='dark'
        )
        
        self.page = await self.context.new_page()
        
        # Apply playwright-stealth to evade bot detection
        await stealth(self.page)

        self.log('init', 'browser', 'stealth initialized')

    # ─────────────────────────────────────────────────────────────────────────
    # BROWSER EXECUTION WORKER: SINGLE ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────────

    async def execute_intent(self, payload: dict) -> dict:
        """
        Main execution worker method. Accepts the strict JSON schema:
        {
          "intent": "SEARCH_AND_ADD" | "MODIFY_CART" | "PLACE_ORDER",
          "data": {
            "restaurant_preference": "string or null",
            "items": [{"name": "string", "quantity": 1, "customizations": []}],
            "delivery_address_tag": "string or null"
          }
        }
        """
        intent = payload.get("intent")
        data = payload.get("data", {})
        
        self.log("execute_intent", intent, "started")
        
        try:
            if intent == "SEARCH_AND_ADD":
                return await self._handle_search_and_add(data)
            elif intent == "MODIFY_CART":
                return await self._handle_modify_cart(data)
            elif intent == "PLACE_ORDER":
                return await self._handle_place_order(data)
            else:
                return self._create_response("FAILED", "Unknown intent")
        except Exception as e:
            self.log("execute_intent", intent, f"CRITICAL FAILURE: {str(e)}")
            screenshot = await self.take_screenshot()
            return self._create_response("FAILED", f"Execution error: {str(e)}", screenshot)

    def _create_response(self, status: str, error_message: str = None, screenshot_path: str = None, current_cart: list = None) -> dict:
        if current_cart is None:
            current_cart = []
        return {
            "status": status,
            "current_cart": current_cart,
            "screenshot_path": screenshot_path,
            "error_message": error_message
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INTENT HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_search_and_add(self, data: dict) -> dict:
        restaurant = data.get("restaurant_preference")
        items = data.get("items", [])
        
        if not items:
            return self._create_response("FAILED", "No items provided to search and add.")
            
        await self.page.goto(BASE_URL, wait_until='domcontentloaded', timeout=40000)
        await self.page.wait_for_timeout(2000)

        added_items_log = []
        
        # Scenario A: Restaurant specified
        if restaurant:
            self.log("execute", "search_restaurant", restaurant)
            url = f"{BASE_URL}/search?query={urllib.parse.quote(restaurant)}"
            await self.page.goto(url, wait_until='domcontentloaded')
            await self.page.wait_for_timeout(3000)
            
            # Find and click the restaurant card
            card = self.page.locator(
                f'[data-testid="restaurant-item"]:has-text("{restaurant}"), [class*="RestaurantCard"]:has-text("{restaurant}")'
            ).first
            
            if await card.is_visible():
                await card.click()
                await self.page.wait_for_timeout(4000)
            else:
                screenshot = await self.take_screenshot()
                return self._create_response("FAILED", f"Could not find restaurant: {restaurant}", screenshot)
                
            # Add items from restaurant menu
            for item in items:
                res = await self._add_item_robust(item.get("name"), item.get("quantity", 1), item.get("customizations", []))
                if res: added_items_log.append(item.get("name"))

        # Scenario B: No Restaurant (Global dish search)
        else:
            for item in items:
                dish_name = item.get("name")
                self.log("execute", "global_search_dish", dish_name)
                url = f"{BASE_URL}/search?query={urllib.parse.quote(dish_name)}"
                await self.page.goto(url, wait_until='domcontentloaded')
                await self.page.wait_for_timeout(3000)
                
                # We are looking at a dish search results page
                res = await self._add_item_robust(dish_name, item.get("quantity", 1), item.get("customizations", []))
                if res: added_items_log.append(dish_name)

        # Sync cart state after all adds
        cart_data = await self.get_cart_contents()
        screenshot = await self.take_screenshot()
        
        if not added_items_log:
            return self._create_response("FAILED", "Could not add any of the requested items.", screenshot, cart_data.get("items", []))
            
        return self._create_response("SUCCESS", None, screenshot, cart_data.get("items", []))

    async def _handle_modify_cart(self, data: dict) -> dict:
        items = data.get("items", [])
        await self.page.goto(f"{BASE_URL}/cart", wait_until='domcontentloaded')
        await self.page.wait_for_timeout(3000)
        
        # The logic here would dynamically modify the cart on the UI.
        # However, Swiggy's cart UI relies heavily on +/- buttons tied to specific items.
        for item in items:
            name = item.get("name")
            action = item.get("action")
            qty = item.get("quantity", 1)
            
            try:
                # Find the cart item container
                cart_item_el = self.page.locator(f'[class*="CartItem"]:has-text("{name}"), [class*="cartItem"]:has-text("{name}")').first
                if not await cart_item_el.is_visible():
                    self.log("modify_cart", name, "Not found in cart UI")
                    continue
                
                # Removing an item (clicking '-' until it disappears)
                if action == "remove" or qty == 0:
                    minus_btn = cart_item_el.locator('[class*="decrement"], [class*="decrease"], button:has-text("-")').first
                    while await cart_item_el.is_visible(timeout=1000):
                        if await minus_btn.is_visible():
                            await minus_btn.click()
                            await self.page.wait_for_timeout(500)
                        else:
                            break
                            
            except Exception as e:
                self.log("modify_cart", name, f"Error: {e}")

        # Fetch final cart state
        cart_data = await self.get_cart_contents()
        screenshot = await self.take_screenshot()
        return self._create_response("SUCCESS", None, screenshot, cart_data.get("items", []))

    async def _handle_place_order(self, data: dict) -> dict:
        await self.page.goto(f"{BASE_URL}/cart", wait_until='domcontentloaded')
        await self.page.wait_for_timeout(3000)
        
        # If cart is empty on the UI, Swiggy usually shows "Cart Empty" text
        if await self.page.locator('text="Cart Empty"').is_visible():
            screenshot = await self.take_screenshot()
            return self._create_response("FAILED", "Cart is empty. Cannot checkout.", screenshot)

        try:
            for sel in ['button:has-text("Proceed to Pay")', 'button:has-text("Place Order")', '[class*="proceedToPay"]']:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await self.page.wait_for_timeout(4000) # Wait for payment gateway / confirmation
                    screenshot = await self.take_screenshot()
                    cart_data = await self.get_cart_contents()
                    return self._create_response("SUCCESS", None, screenshot, cart_data.get("items", []))
            
            screenshot = await self.take_screenshot()
            return self._create_response("FAILED", "Checkout button not found on cart page.", screenshot)
        except Exception as e:
            screenshot = await self.take_screenshot()
            return self._create_response("FAILED", f"Error during checkout: {e}", screenshot)


    # ─────────────────────────────────────────────────────────────────────────
    # ROBUST SEMANTIC ACTION HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    async def _add_item_robust(self, item_name: str, quantity: int, customizations: list) -> bool:
        """
        Locates the specific item container semantically, checks for Out of Stock,
        and clicks the 'ADD' button strictly scoped inside that container.
        """
        try:
            # 1. Locate the container
            container_selectors = ['[data-testid="normal-dish-item"]', '[class*="MenuItem"]', '[class*="DishCard"]']
            item_container = None
            
            for sel in container_selectors:
                # Use robust regex match for item name inside the container
                el = self.page.locator(sel, has_text=re.compile(re.escape(item_name), re.IGNORECASE)).first
                if await el.is_visible(timeout=2000):
                    item_container = el
                    break
            
            if not item_container:
                self.log("add_item", item_name, "Container not found")
                return False

            # 2. Check OOS
            if await item_container.locator('[class*="OutOfStock"],[class*="outOfStock"]').count() > 0:
                self.log("add_item", item_name, "Out of stock")
                return False

            # 3. Scoped ADD click
            add_selectors = ['[data-testid="add-to-cart"]', 'button:has-text("ADD")', 'button:has-text("Add")', '[class*="addBtn"]']
            added = False
            
            for sel in add_selectors:
                btn = item_container.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click(force=True)
                    added = True
                    await self.page.wait_for_timeout(1000)
                    break
                    
            if not added:
                # Fallback: click the whole container or generic button
                try:
                    any_btn = item_container.locator('button').first
                    if await any_btn.is_visible(timeout=1000):
                        await any_btn.click(force=True)
                        added = True
                        await self.page.wait_for_timeout(1000)
                except:
                    pass

            if not added:
                self.log("add_item", item_name, "Could not find add button inside container")
                return False

            # 4. Handle Modals and Quantity
            await self._handle_customization_modal(customizations)
            
            # If qty > 1, we must click the scoped "+" button
            if quantity > 1:
                for _ in range(1, quantity):
                    plus_selectors = ['[data-testid="increase-count"]', '[class*="increaseCount"]', 'button:has-text("+")']
                    for sel in plus_selectors:
                        plus_btn = item_container.locator(sel).last
                        if await plus_btn.is_visible(timeout=1000):
                            await plus_btn.click()
                            await self.page.wait_for_timeout(500)
                            break
                            
            self.log("add_item", item_name, "SUCCESS")
            return True

        except Exception as e:
            self.log("add_item", item_name, f"Error: {e}")
            return False

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
            await self.page.wait_for_timeout(1000)
        except:
            pass

    async def get_cart_contents(self) -> dict:
        try:
            await self.page.goto(f"{BASE_URL}/cart", wait_until='domcontentloaded', timeout=15000)
            await self.page.wait_for_timeout(2000)
            
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
            return {"success": True, **data}
        except Exception as err:
            return {"success": False, "error": str(err), "items": []}

    # ─────────────────────────────────────────────────────────────────────────
    # LOGIN FLOW (Preserved for initial auth)
    # ─────────────────────────────────────────────────────────────────────────

    async def enter_phone(self, phone: str) -> dict:
        try:
            self.log('login', 'navigating to swiggy', 'start')
            await self.page.goto(BASE_URL, wait_until='domcontentloaded', timeout=40000)
            await self.page.wait_for_timeout(3000)
            screenshot = await self.take_screenshot()

            sign_in_clicked = await self._click_sign_in()
            if not sign_in_clicked:
                await self.page.goto(f"{BASE_URL}/login", wait_until='domcontentloaded', timeout=20000)
                await self.page.wait_for_timeout(2000)

            phone_input = await self._wait_for_phone_input()
            if not phone_input:
                screenshot = await self.take_screenshot()
                return {"success": False, "error": "Phone input not found on Swiggy.", "screenshot": screenshot}

            await phone_input.click(click_count=3)
            await phone_input.fill('')
            await self.page.wait_for_timeout(300)
            await phone_input.type(phone, delay=100)
            await self.page.wait_for_timeout(600)

            screenshot = await self.take_screenshot()
            submitted = await self._click_continue_button()
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
            '[data-testid*="login"]', '[data-testid*="signin"]'
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
            'input[placeholder*="mobile" i]', 'input[maxlength="10"]'
        ]
        deadline = time.time() + (timeout / 1000)
        while time.time() < deadline:
            for sel in selectors:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible(timeout=500):
                        return el
                except:
                    continue
            await self.page.wait_for_timeout(500)
        return None

    async def _click_continue_button(self) -> bool:
        selectors = [
            'button:has-text("Continue")', 'button:has-text("continue")',
            'button:has-text("GET OTP")', 'button:has-text("Get OTP")'
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

            single_selectors = ['input[type="tel"][maxlength="6"]', 'input[type="number"][maxlength="6"]', 'input[name="otp"]']

            filled_single = False
            for sel in single_selectors:
                try:
                    inp = self.page.locator(sel).first
                    if await inp.is_visible(timeout=2000):
                        await inp.click(click_count=3)
                        await inp.fill(otp)
                        filled_single = True
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

            if not filled_single:
                screenshot = await self.take_screenshot()
                return {"success": False, "error": "OTP input not found.", "screenshot": screenshot}

            await self.page.wait_for_timeout(800)
            for sel in ['button:has-text("Verify")', 'button:has-text("Submit")']:
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
                return {"success": True, "screenshot": screenshot}
            return {"success": False, "error": "OTP incorrect or expired.", "screenshot": screenshot}
        except Exception as err:
            screenshot = await self.take_screenshot()
            return {"success": False, "error": str(err), "screenshot": screenshot}

    async def _check_login_status(self) -> bool:
        try:
            if '/login' in self.page.url or '/otp' in self.page.url:
                return False
            for sel in ['[class*="userProfile"]', '[class*="profileIcon"]', '[data-testid*="profile"]']:
                if await self.page.query_selector(sel): return True
            title = await self.page.title()
            if 'swiggy' in title.lower() and 'login' not in title.lower(): return True
            return False
        except:
            return False

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
