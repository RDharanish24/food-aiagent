import time
import base64
import urllib.parse
import re
import os
import json
import shutil
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth import Stealth

BASE_URL = 'https://www.swiggy.com'

# Default geolocation: Bangalore
DEFAULT_LAT = '12.9716'
DEFAULT_LNG = '77.5946'
DEFAULT_ADDRESS = 'Bangalore, Karnataka, India'

class FoodOrderingAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
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
        
        # Define persistent profile path
        self.profile_dir = os.path.join(os.getcwd(), f"tmp_playwright_profile_{self.session_id}")
        os.makedirs(self.profile_dir, exist_ok=True)
        
        # Launch persistent context for stealth and session retention
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080',
            ],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-IN',
            timezone_id='Asia/Kolkata',
            permissions=['geolocation'],
            geolocation={'latitude': float(DEFAULT_LAT), 'longitude': float(DEFAULT_LNG)},
            color_scheme='light'
        )
        
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # Apply playwright-stealth to evade bot detection
        await Stealth().apply_stealth_async(self.page)
        
        # Set location cookies so Swiggy knows our delivery area
        await self._set_location_cookies(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ADDRESS)

        self.log('init', 'browser', 'stealth persistent context initialized')

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

    async def _set_location_cookies(self, lat: str, lng: str, address: str):
        """
        Sets Swiggy location cookies directly. This is the most reliable way
        to tell Swiggy's SPA our delivery location without fragile UI interaction.
        """
        await self.context.add_cookies([
            {"name": "lat", "value": lat, "domain": ".swiggy.com", "path": "/"},
            {"name": "lng", "value": lng, "domain": ".swiggy.com", "path": "/"},
            {
                "name": "userLocation",
                "value": json.dumps({
                    "lat": lat, "lng": lng,
                    "address": address, "id": "", "annotation": address.split(',')[0]
                }),
                "domain": ".swiggy.com", "path": "/"
            },
        ])
        self.log("location_cookies", "set", f"{address} ({lat}, {lng})")

    async def _ensure_location_set(self) -> bool:
        """
        Ensures location cookies are set. Uses cookie-based approach as primary,
        falling back to UI interaction if needed.
        """
        try:
            self.log("location_check", "started", f"Page URL: {self.page.url}")
            
            # Check if location cookies already exist
            cookies = await self.context.cookies("https://www.swiggy.com")
            has_lat = any(c['name'] == 'lat' and c['value'] for c in cookies)
            has_lng = any(c['name'] == 'lng' and c['value'] for c in cookies)
            
            if has_lat and has_lng:
                self.log("location_check", "cookies_present", "Location already set via cookies")
                return True
            
            # Set cookies if missing
            await self._set_location_cookies(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ADDRESS)
            return True
        except Exception as e:
            self.log("location", "Error setting location", str(e))
            # Last resort: set cookies anyway
            try:
                await self._set_location_cookies(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ADDRESS)
                return True
            except:
                return False

    async def _search_item_or_restaurant(self, query: str, is_dish: bool = True) -> bool:
        """
        Navigates to /search, types the query using character-by-character input
        (to trigger React autocomplete), clicks the best suggestion, and waits
        for actual results to load past skeleton state.
        """
        try:
            # Navigate to search page
            if "/search" not in self.page.url or "query=" in self.page.url:
                try:
                    await self.page.goto(f"{BASE_URL}/search", wait_until='domcontentloaded', timeout=20000)
                except Exception as e:
                    self.log("goto_search", "warning", f"Search page navigation: {e}")
            
            # Wait for search input to become visible
            try:
                await self.page.wait_for_selector(
                    'input[placeholder*="Search for"]', state='visible', timeout=15000
                )
            except:
                self.log("search", "warning", "Search input not found after wait, retrying...")
                await self.page.wait_for_timeout(3000)
            
            # Find the search input
            search_input = None
            for sel in ['input[placeholder*="Search for"]', 'input[placeholder*="search" i]', 'input[type="text"]']:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    search_input = el
                    break
                    
            if not search_input:
                self.log("search", "error", "Search input not found on page")
                return False
            
            # Clear and type query character-by-character (triggers React onChange)
            await search_input.click()
            await search_input.focus()
            # Triple-click to select all, then delete
            await search_input.click(click_count=3)
            await self.page.keyboard.press('Backspace')
            await self.page.wait_for_timeout(300)
            await search_input.type(query, delay=80)
            self.log("search", "typed_query", query)
            
            # Wait for autocomplete suggestions to appear
            try:
                await self.page.wait_for_selector('button.xN32R', state='visible', timeout=8000)
                self.log("search", "suggestions", "Autocomplete suggestions appeared")
            except:
                self.log("search", "warning", "No autocomplete suggestions, pressing Enter")
                await search_input.press('Enter')
                await self._wait_for_search_results()
                return True
            
            # Click the best matching suggestion
            suggestion_clicked = False
            suggestion_buttons = await self.page.locator('button.xN32R').all()
            
            # Prefer "Dish" type suggestions for dish searches, "Restaurant" for restaurant searches
            prefer_type = "Dish" if is_dish else "Restaurant"
            
            for btn in suggestion_buttons:
                try:
                    text = await btn.text_content()
                    if not text:
                        continue
                    text = text.strip()
                    
                    # Check if this suggestion matches our query and preferred type
                    if query.lower() in text.lower() and prefer_type in text:
                        self.log("search", "clicking_suggestion", text)
                        await btn.click()
                        suggestion_clicked = True
                        break
                except:
                    continue
            
            # Fallback: click first suggestion if no preferred match found
            if not suggestion_clicked:
                first_btn = self.page.locator('button.xN32R').first
                if await first_btn.is_visible(timeout=2000):
                    text = await first_btn.text_content()
                    self.log("search", "clicking_first_suggestion", text.strip() if text else "unknown")
                    await first_btn.click()
                    suggestion_clicked = True
            
            if not suggestion_clicked:
                # Final fallback: press Enter
                await search_input.press('Enter')
            
            # Wait for actual results to load (past skeleton placeholders)
            await self._wait_for_search_results()
            return True
            
        except Exception as e:
            self.log("search", "error", str(e))
            return False
    
    async def _wait_for_search_results(self):
        """
        Waits for search results to fully render by checking for the rupee symbol
        in the page text, which indicates prices have loaded past the skeleton state.
        """
        try:
            await self.page.wait_for_function(
                "() => document.body.innerText.includes('\u20B9')",
                timeout=25000
            )
            self.log("search", "results_loaded", "Content rendered (prices visible)")
        except:
            self.log("search", "warning", "Timeout waiting for results content")
        
        # Extra buffer for remaining content to load
        await self.page.wait_for_timeout(2000)

    async def _handle_search_and_add(self, data: dict) -> dict:
        restaurant = data.get("restaurant_preference")
        items = data.get("items", [])
        
        if not items:
            return self._create_response("FAILED", "No items provided to search and add.")
            
        # Get current cart contents to avoid double-ordering
        cart_data = await self.get_cart_contents()
        existing_cart_items = cart_data.get("items", []) if cart_data.get("success") else []
        existing_item_names = {item["name"].lower() for item in existing_cart_items}
        self.log("cart_check", "existing_cart_items", str(existing_item_names))

        # Ensure location cookies are set
        await self._ensure_location_set()

        added_items_log = []
        menu_search_selectors = [
            'input[placeholder*="Search for dishes"]',
            'input[placeholder*="Search in menu"]',
            'input[placeholder*="search" i]',
            'input[class*="search" i]',
            '[data-testid="menu-search"] input'
        ]
        
        # Scenario A: Restaurant specified
        if restaurant:
            self.log("execute", "search_restaurant", restaurant)
            await self._search_item_or_restaurant(restaurant, is_dish=False)
            
            # Find and click the restaurant link/card
            # Swiggy search results use <a> tags with class _3VPpz for restaurant links
            clicked = False
            restaurant_link_selectors = [
                'a._3VPpz',  # Swiggy's actual restaurant link class
                'a[href*="/city/"]',
                'a[href*="/restaurant"]',
                '[data-testid="restaurant-item"]',
            ]
            for sel in restaurant_link_selectors:
                elements = await self.page.locator(sel).all()
                for el in elements:
                    try:
                        text = await el.text_content()
                        if text and restaurant.lower() in text.lower():
                            await el.scroll_into_view_if_needed()
                            await el.click()
                            clicked = True
                            self.log("restaurant", "clicked", text.strip()[:100])
                            break
                    except:
                        continue
                if clicked:
                    break
            
            if not clicked:
                # Click the first restaurant result as fallback
                first_link = self.page.locator('a._3VPpz, a[href*="/city/"]').first
                if await first_link.is_visible(timeout=3000):
                    await first_link.click()
                    clicked = True
            
            if clicked:
                await self.page.wait_for_timeout(5000)
            else:
                screenshot = await self.take_screenshot()
                return self._create_response("FAILED", f"Could not find restaurant: {restaurant}", screenshot)
                
            # Add items from restaurant menu
            for item in items:
                item_name = item.get("name")
                
                if self._is_item_in_cart(item_name, existing_item_names):
                    self.log("add_item", item_name, "Already in cart, skipping")
                    added_items_log.append(item_name)
                    continue
                
                # Search the item inside restaurant menu
                menu_search_input = None
                for sel in menu_search_selectors:
                    el = self.page.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        menu_search_input = el
                        break
                
                if menu_search_input:
                    self.log("menu_search", f"Searching menu for {item_name}", "")
                    await menu_search_input.click()
                    await menu_search_input.click(click_count=3)
                    await self.page.keyboard.press('Backspace')
                    await menu_search_input.type(item_name, delay=80)
                    await self.page.wait_for_timeout(2000)
                
                res = await self._add_item_robust(item_name, item.get("quantity", 1), item.get("customizations", []))
                if res:
                    added_items_log.append(item_name)
                    existing_item_names.add(item_name.lower())

        # Scenario B: No Restaurant (Global dish search)
        else:
            for item in items:
                dish_name = item.get("name")
                
                if self._is_item_in_cart(dish_name, existing_item_names):
                    self.log("add_item", dish_name, "Already in cart, skipping")
                    added_items_log.append(dish_name)
                    continue
                
                self.log("execute", "global_search_dish", dish_name)
                await self._search_item_or_restaurant(dish_name, is_dish=True)
                
                # On the search results page, dish cards are directly visible with ADD buttons.
                # Use [data-testid="search-pl-dish-first-v2-card"] as the outer card container
                # and [data-testid="normal-dish-item"] as the inner dish item.
                # We can add directly from the search results page!
                res = await self._add_item_robust(
                    dish_name, item.get("quantity", 1), item.get("customizations", [])
                )
                if res:
                    added_items_log.append(dish_name)
                    existing_item_names.add(dish_name.lower())

        # Sync cart state after all adds
        cart_data = await self.get_cart_contents()
        screenshot = await self.take_screenshot()
        
        if not added_items_log:
            return self._create_response("FAILED", "Could not add any of the requested items.", screenshot, cart_data.get("items", []))
            
        return self._create_response("SUCCESS", None, screenshot, cart_data.get("items", []))
    
    def _is_item_in_cart(self, item_name: str, existing_item_names: set) -> bool:
        """Check if an item is already in the cart (fuzzy name match)."""
        for existing_name in existing_item_names:
            if item_name.lower() in existing_name or existing_name in item_name.lower():
                return True
        return False

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
        
        Swiggy DOM structure (from real analysis):
        - Outer card: [data-testid="search-pl-dish-first-v2-card"] (class: _1K_JA _3Y0kn)
        - Inner dish: [data-testid="normal-dish-item"] (class: sc-tagGq dqUmYU)
        - ADD button: button with class containing 'add-button-center-container'
        - Restaurant link: a._3VPpz
        """
        try:
            # 1. Locate the dish container
            # Use multiple selectors, ordered by specificity for Swiggy's real DOM
            container_selectors = [
                '[data-testid="normal-dish-item"]',
                '[data-testid="search-pl-dish-first-v2-card"]',
                '[class*="MenuItem"]',
                '[class*="DishCard"]',
            ]
            item_container = None
            
            for sel in container_selectors:
                # Use case-insensitive regex match for item name inside the container
                el = self.page.locator(sel, has_text=re.compile(re.escape(item_name), re.IGNORECASE)).first
                try:
                    if await el.is_visible(timeout=3000):
                        item_container = el
                        self.log("add_item", item_name, f"Container found with: {sel}")
                        break
                except:
                    continue
            
            if not item_container:
                self.log("add_item", item_name, "Container not found, trying scroll...")
                # Try scrolling down to find the item
                for _ in range(3):
                    await self.page.evaluate("window.scrollBy(0, 600)")
                    await self.page.wait_for_timeout(1000)
                    for sel in container_selectors:
                        el = self.page.locator(sel, has_text=re.compile(re.escape(item_name), re.IGNORECASE)).first
                        try:
                            if await el.is_visible(timeout=1000):
                                item_container = el
                                break
                        except:
                            continue
                    if item_container:
                        break
                
                if not item_container:
                    self.log("add_item", item_name, "Container not found after scroll")
                    return False

            # 2. Check OOS (Out of Stock)
            try:
                oos_count = await item_container.locator('[class*="OutOfStock" i]').count()
                if oos_count > 0:
                    self.log("add_item", item_name, "Out of stock")
                    return False
            except:
                pass

            # 3. Scroll container into view
            try:
                await item_container.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
            except:
                pass

            # 4. Click ADD button (scoped inside the container)
            # Swiggy uses both "ADD" and "Add" text, and styled-components classes
            add_selectors = [
                'button.add-button-center-container',
                'button:has-text("ADD")',
                'button:has-text("Add")',
                '[data-testid="add-to-cart"]',
                '[class*="addBtn"]',
            ]
            added = False
            
            for sel in add_selectors:
                try:
                    btn = item_container.locator(sel).first
                    if await btn.is_visible(timeout=1500):
                        await btn.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(300)
                        await btn.click(force=True)
                        added = True
                        self.log("add_item", item_name, f"Clicked ADD via: {sel}")
                        await self.page.wait_for_timeout(1500)
                        break
                except:
                    continue
                    
            if not added:
                # Fallback: try any button inside the container
                try:
                    buttons = await item_container.locator('button').all()
                    for btn in buttons:
                        btn_text = await btn.text_content()
                        if btn_text and btn_text.strip().upper() in ('ADD', 'ADD +'):
                            await btn.click(force=True)
                            added = True
                            self.log("add_item", item_name, "Clicked ADD via button text fallback")
                            await self.page.wait_for_timeout(1500)
                            break
                except:
                    pass

            if not added:
                self.log("add_item", item_name, "Could not find ADD button inside container")
                return False

            # 5. Handle customization modal (if it appears)
            await self._handle_customization_modal(customizations)
            
            # 6. Handle quantity (if qty > 1, click "+" button)
            if quantity > 1:
                for _ in range(1, quantity):
                    plus_selectors = [
                        '[data-testid="increase-count"]',
                        '[class*="increaseCount"]',
                        'button:has-text("+")',
                    ]
                    for sel in plus_selectors:
                        try:
                            plus_btn = item_container.locator(sel).last
                            if await plus_btn.is_visible(timeout=1500):
                                await plus_btn.click()
                                await self.page.wait_for_timeout(500)
                                break
                        except:
                            continue
                            
            self.log("add_item", item_name, f"SUCCESS (qty={quantity})")
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
        """Navigate to cart page and extract cart items from the DOM."""
        try:
            try:
                await self.page.goto(f"{BASE_URL}/cart", wait_until='domcontentloaded', timeout=15000)
            except Exception as e:
                self.log("goto_cart", "warning", f"Cart page navigation: {e}")
            await self.page.wait_for_timeout(3000)
            
            js_code = """
                () => {
                    const items = [];
                    // Try multiple cart item selectors
                    const selectors = ['[class*="CartItem"]', '[class*="cartItem"]', '[class*="itemContainer"]'];
                    for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach(el => {
                            const name = (el.querySelector('[class*="name" i]') || el.querySelector('h4') || el.querySelector('h3'))?.textContent?.trim();
                            const qty = el.querySelector('[class*="count" i],[class*="quantity" i]')?.textContent?.trim() || '1';
                            const price = el.querySelector('[class*="price" i]')?.textContent?.trim();
                            if (name) items.push({ name, quantity: parseInt(qty) || 1, price });
                        });
                        if (items.length > 0) break;
                    }
                    const total = document.querySelector('[class*="TotalPayable" i],[class*="grandTotal" i],[class*="totalAmount" i]')?.textContent?.trim();
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
        if self.context:
            await self.context.close()
        if self._playwright:
            await self._playwright.stop()
        # Clean up persistent profile directory
        if hasattr(self, 'profile_dir') and os.path.exists(self.profile_dir):
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
            except Exception as e:
                print(f"[Agent {self.session_id}] Error cleaning profile dir: {e}")


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
