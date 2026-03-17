import { chromium } from 'playwright';
import dotenv from 'dotenv';
dotenv.config();

const BASE_URL = 'https://www.swiggy.com';

export class FoodOrderingAgent {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.browser = null;
    this.context = null;
    this.page = null;
    this.actionLog = [];
    this.isLoggedIn = false;
  }

  log(action, target, result) {
    const entry = { action, target, result, timestamp: new Date() };
    this.actionLog.push(entry);
    console.log(`[Agent ${this.sessionId}] ${action} | ${target} | ${result}`);
    return entry;
  }

  async init() {
    this.browser = await chromium.launch({
      headless: false, // headful — Swiggy detects headless easily
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--start-maximized',
      ]
    });
    this.context = await this.browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
      viewport: null, // use full window size
      locale: 'en-IN',
      timezoneId: 'Asia/Kolkata',
    });
    this.page = await this.context.newPage();

    // Remove all automation flags
    await this.page.addInitScript(() => {
      delete Object.getPrototypeOf(navigator).webdriver;
      window.navigator.chrome = { runtime: {} };
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
      Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
    });

    this.log('init', 'browser', 'success');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOGIN FLOW
  // ─────────────────────────────────────────────────────────────────────────

  async enterPhone(phone) {
    try {
      this.log('login', 'navigating to swiggy', 'start');

      // Step 1: Load Swiggy homepage
      await this.page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 40000 });
      await this.page.waitForTimeout(3000);

      // Step 2: Take screenshot so we can debug what the page looks like
      let screenshot = await this.takeScreenshot();

      // Step 3: Click "Sign In" — try many selectors
      const signInClicked = await this._clickSignIn();
      this.log('login', 'sign in button', signInClicked ? 'clicked' : 'not found, trying /login');

      if (!signInClicked) {
        // Fallback: go to /login directly
        await this.page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 20000 });
        await this.page.waitForTimeout(2000);
      }

      // Step 4: Wait for phone input to appear
      this.log('login', 'waiting for phone input', 'start');
      const phoneInput = await this._waitForPhoneInput();

      if (!phoneInput) {
        screenshot = await this.takeScreenshot();
        // Log the page HTML for debugging
        const bodyText = await this.page.evaluate(() => document.body.innerText.substring(0, 500));
        this.log('login', 'phone input', `NOT FOUND. Page text: ${bodyText}`);
        return { success: false, error: 'Phone input not found on Swiggy. The site may have changed its layout.', screenshot };
      }

      // Step 5: Type phone number
      await phoneInput.click({ clickCount: 3 }); // select all first
      await phoneInput.fill('');
      await this.page.waitForTimeout(300);
      await phoneInput.type(phone, { delay: 100 }); // human-like typing
      await this.page.waitForTimeout(600);

      this.log('login', 'phone entered', phone);
      screenshot = await this.takeScreenshot();

      // Step 6: Click the submit / Continue button
      const submitted = await this._clickContinueButton();
      this.log('login', 'continue button', submitted ? 'clicked' : 'not found, trying Enter key');

      if (!submitted) {
        await phoneInput.press('Enter');
      }

      await this.page.waitForTimeout(3000);
      screenshot = await this.takeScreenshot();

      return { success: true, screenshot };

    } catch (err) {
      this.log('enterPhone', 'error', err.message);
      const screenshot = await this.takeScreenshot();
      return { success: false, error: err.message, screenshot };
    }
  }

  async _clickSignIn() {
    const selectors = [
      // Text-based
      'a:has-text("Sign in")',
      'a:has-text("Sign In")',
      'button:has-text("Sign in")',
      'button:has-text("Sign In")',
      // Swiggy-specific class patterns
      '[class*="LoginSignupBtn"]',
      '[class*="login-signup"]',
      '[class*="signIn"]',
      '[class*="SignIn"]',
      '[data-testid*="login"]',
      '[data-testid*="signin"]',
      // Generic
      'a[href*="login"]',
      'a[href*="signin"]',
    ];

    for (const sel of selectors) {
      try {
        const el = this.page.locator(sel).first();
        if (await el.isVisible({ timeout: 2000 })) {
          await el.click();
          await this.page.waitForTimeout(2000);
          return true;
        }
      } catch { continue; }
    }
    return false;
  }

  async _waitForPhoneInput(timeout = 12000) {
    const selectors = [
      'input[type="tel"]',
      'input[name="mobile"]',
      'input[name="phone"]',
      'input[autocomplete="tel"]',
      'input[placeholder*="mobile" i]',
      'input[placeholder*="phone" i]',
      'input[placeholder*="number" i]',
      'input[placeholder*="Enter" i]',
      '[class*="PhoneInput"] input',
      '[class*="phoneInput"] input',
      '[class*="mobileInput"] input',
      '[class*="MobileInput"] input',
      '[class*="LoginInput"] input',
      '[class*="loginInput"] input',
      'input[maxlength="10"]',
      // Last resort: any visible input in the login modal
      '[class*="modal"] input',
      '[class*="Modal"] input',
      '[class*="popup"] input',
      '[class*="Popup"] input',
      'input[type="number"]',
      'input[type="text"]',
    ];

    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      for (const sel of selectors) {
        try {
          const el = this.page.locator(sel).first();
          if (await el.isVisible({ timeout: 500 })) {
            this.log('_waitForPhoneInput', sel, 'FOUND');
            return el;
          }
        } catch { continue; }
      }
      await this.page.waitForTimeout(500);
    }
    return null;
  }

  async _clickContinueButton() {
    const selectors = [
      'button:has-text("Continue")',
      'button:has-text("continue")',
      'button:has-text("GET OTP")',
      'button:has-text("Get OTP")',
      'button:has-text("Send OTP")',
      'button:has-text("Login")',
      'button:has-text("Next")',
      'button[type="submit"]',
      '[class*="ContinueBtn"]',
      '[class*="continueBtn"]',
      '[class*="SubmitBtn"]',
      '[class*="submitBtn"]',
      '[class*="LoginBtn"]',
      '[class*="loginBtn"]',
    ];

    for (const sel of selectors) {
      try {
        const btn = this.page.locator(sel).first();
        if (await btn.isVisible({ timeout: 2000 })) {
          await btn.click();
          return true;
        }
      } catch { continue; }
    }
    return false;
  }

  async enterOTP(otp) {
    try {
      await this.page.waitForTimeout(1000);
      let screenshot = await this.takeScreenshot();

      // Try single OTP input (some flows use one box)
      const singleSelectors = [
        'input[type="tel"][maxlength="6"]',
        'input[type="number"][maxlength="6"]',
        'input[placeholder*="OTP" i]',
        'input[placeholder*="otp" i]',
        'input[name="otp"]',
        '[class*="OtpInput"] input',
        '[class*="otpInput"] input',
      ];

      let filledSingle = false;
      for (const sel of singleSelectors) {
        try {
          const input = this.page.locator(sel).first();
          if (await input.isVisible({ timeout: 2000 })) {
            await input.click({ clickCount: 3 });
            await input.fill(otp);
            filledSingle = true;
            this.log('enterOTP', 'single input', 'filled');
            break;
          }
        } catch { continue; }
      }

      // Try 4–6 separate digit boxes (Swiggy's most common OTP UI)
      if (!filledSingle) {
        const digitBoxes = await this.page.$$('input[maxlength="1"]');
        if (digitBoxes.length >= 4) {
          for (let i = 0; i < Math.min(digitBoxes.length, otp.length); i++) {
            await digitBoxes[i].click();
            await digitBoxes[i].fill(otp[i]);
            await this.page.waitForTimeout(120);
          }
          filledSingle = true;
          this.log('enterOTP', `${digitBoxes.length} digit boxes`, 'filled');
        }
      }

      if (!filledSingle) {
        screenshot = await this.takeScreenshot();
        return { success: false, error: 'OTP input not found. Please check the OTP screen.', screenshot };
      }

      await this.page.waitForTimeout(800);

      // Click Verify if needed
      for (const sel of ['button:has-text("Verify")', 'button:has-text("Submit")', 'button:has-text("Continue")', 'button[type="submit"]']) {
        try {
          const btn = this.page.locator(sel).first();
          if (await btn.isVisible({ timeout: 1500 })) { await btn.click(); break; }
        } catch { continue; }
      }

      await this.page.waitForTimeout(4000);

      // Check login success
      const loggedIn = await this._checkLoginStatus();
      screenshot = await this.takeScreenshot();

      if (loggedIn) {
        this.isLoggedIn = true;
        this.log('enterOTP', 'login', 'SUCCESS');
        return { success: true, screenshot };
      }

      return { success: false, error: 'OTP incorrect or expired. Please try again.', screenshot };

    } catch (err) {
      const screenshot = await this.takeScreenshot();
      return { success: false, error: err.message, screenshot };
    }
  }

  async _checkLoginStatus() {
    try {
      const url = this.page.url();
      if (url.includes('/login') || url.includes('/otp')) return false;

      const loggedInSelectors = [
        '[class*="userProfile"]',
        '[class*="UserProfile"]',
        '[class*="profileIcon"]',
        '[aria-label*="account" i]',
        'img[alt*="profile" i]',
        '[class*="avatar"]',
        '[data-testid*="profile"]',
      ];
      for (const sel of loggedInSelectors) {
        const el = await this.page.$(sel);
        if (el) return true;
      }
      // Also check if page title / content suggests we are on home page
      const title = await this.page.title();
      if (title.toLowerCase().includes('swiggy') && !title.toLowerCase().includes('login')) return true;

      return false;
    } catch { return false; }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SEARCH FLOW
  // ─────────────────────────────────────────────────────────────────────────

  async searchFood(query) {
    try {
      this.log('search', query, 'start');

      await this.page.goto(`${BASE_URL}/search?query=${encodeURIComponent(query)}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await this.page.waitForTimeout(3500);

      // Also type into search bar if present
      try {
        const searchBar = this.page.locator('input[placeholder*="Search" i], [class*="SearchBar"] input').first();
        if (await searchBar.isVisible({ timeout: 2000 })) {
          await searchBar.click();
          await searchBar.fill('');
          await searchBar.type(query, { delay: 80 });
          await this.page.waitForTimeout(2000);
        }
      } catch { }

      const results = await this.page.evaluate(() => {
        const items = [];

        // Restaurant card selectors (Swiggy 2024 DOM)
        const cardSelectors = [
          '[data-testid="restaurant-item"]',
          '[class*="RestaurantCard"]',
          '[class*="restaurantCard"]',
          '[class*="Restaurant_"] > a',
          'a[href*="/city/"]',
          'a[href*="restaurant"]',
        ];

        for (const sel of cardSelectors) {
          const cards = document.querySelectorAll(sel);
          if (cards.length > 0) {
            cards.forEach(card => {
              const name = (
                card.querySelector('[class*="name"],[class*="Name"],h3,h4,[class*="title"]')
              )?.textContent?.trim();
              const cuisine = card.querySelector('[class*="cuisines"],[class*="Cuisines"],[class*="subtext"]')?.textContent?.trim();
              const rating = card.querySelector('[class*="rating"],[class*="Rating"],[class*="star"]')?.textContent?.trim();
              const deliveryTime = card.querySelector('[class*="time"],[class*="Time"],[class*="delivery"]')?.textContent?.trim();
              const costForTwo = card.querySelector('[class*="cost"],[class*="Cost"],[class*="price"]')?.textContent?.trim();
              const imgEl = card.querySelector('img');
              const img = imgEl?.src || null;
              const anchor = card.tagName === 'A' ? card : card.closest('a') || card.querySelector('a');
              const href = anchor?.href || null;
              if (name) items.push({ type: 'restaurant', name, cuisine, rating, deliveryTime, costForTwo, img, url: href });
            });
            break;
          }
        }

        // Dish results fallback
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
      });

      this.log('search', query, `${results.length} results`);
      const screenshot = await this.takeScreenshot();
      return { success: true, results, query, screenshot };

    } catch (err) {
      this.log('search', query, `ERROR: ${err.message}`);
      return { success: false, error: err.message, results: [] };
    }
  }

  async navigateToRestaurant(url) {
    try {
      await this.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await this.page.waitForTimeout(3000);
      this.log('navigate', url, 'success');
      const menuItems = await this.scrapeMenuItems();
      const screenshot = await this.takeScreenshot();
      return { success: true, menuItems, screenshot };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  async scrapeMenuItems() {
    try {
      await this.page.waitForTimeout(2000);
      return await this.page.evaluate(() => {
        const items = [];
        const selectors = ['[data-testid="normal-dish-item"]', '[class*="MenuItem"]', '[class*="menuItem"]', '[class*="DishInfo"]'];
        for (const sel of selectors) {
          const els = document.querySelectorAll(sel);
          if (els.length > 0) {
            els.forEach(el => {
              const name = (el.querySelector('[data-testid="item-name"]') || el.querySelector('[class*="name"]') || el.querySelector('h4'))?.textContent?.trim();
              const price = el.querySelector('[class*="price"]')?.textContent?.trim();
              const available = !el.querySelector('[class*="OutOfStock"],[class*="outOfStock"]');
              const img = el.querySelector('img')?.src;
              if (name) items.push({ name, price, available, img });
            });
            break;
          }
        }
        return items.slice(0, 20);
      });
    } catch { return []; }
  }

  async addItemToCart(itemName, quantity = 1, customizations = []) {
    try {
      const locators = [
        `[data-testid="normal-dish-item"]:has-text("${itemName}")`,
        `[class*="MenuItem"]:has-text("${itemName}")`,
        `[class*="DishInfo"]:has-text("${itemName}")`,
      ];
      let itemEl = null;
      for (const loc of locators) {
        try {
          const el = this.page.locator(loc).first();
          if (await el.isVisible({ timeout: 3000 })) { itemEl = el; break; }
        } catch { continue; }
      }
      if (!itemEl) return { success: false, error: `"${itemName}" not found`, outOfStock: false };

      const isOOS = await itemEl.locator('[class*="OutOfStock"],[class*="outOfStock"]').count() > 0;
      if (isOOS) return { success: false, error: `"${itemName}" is out of stock`, outOfStock: true };

      let added = false;
      for (const sel of ['[data-testid="add-to-cart"]', 'button:has-text("ADD")', 'button:has-text("Add")', '[class*="addBtn"]']) {
        try {
          const btn = itemEl.locator(sel).first();
          if (await btn.isVisible({ timeout: 2000 })) { await btn.click(); added = true; await this.page.waitForTimeout(800); break; }
        } catch { continue; }
      }

      await this._handleCustomizationModal(customizations);
      if (quantity > 1) await this._adjustQuantity(quantity);
      const screenshot = await this.takeScreenshot();
      return { success: added, itemName, quantity, screenshot };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  async _handleCustomizationModal(customizations = []) {
    try {
      await this.page.waitForTimeout(800);
      const modal = await this.page.$('[class*="ItemModal"],[class*="Customisation"],[class*="customisation"]');
      if (!modal) return;
      for (const c of customizations) {
        try {
          const opt = this.page.locator(`label:has-text("${c}"),[class*="option"]:has-text("${c}")`).first();
          if (await opt.isVisible({ timeout: 1000 })) await opt.click();
        } catch { continue; }
      }
      for (const sel of ['button:has-text("Done")', 'button:has-text("Add Item")', 'button:has-text("Confirm")']) {
        try {
          const btn = this.page.locator(sel).first();
          if (await btn.isVisible({ timeout: 1000 })) { await btn.click(); break; }
        } catch { continue; }
      }
    } catch { }
  }

  async _adjustQuantity(targetQty) {
    for (let i = 1; i < targetQty; i++) {
      for (const sel of ['[data-testid="increase-count"]', '[class*="increaseCount"]', 'button:has-text("+")']) {
        try {
          const btn = this.page.locator(sel).last();
          if (await btn.isVisible({ timeout: 1000 })) { await btn.click(); await this.page.waitForTimeout(300); break; }
        } catch { continue; }
      }
    }
  }

  async getCartContents() {
    try {
      await this.page.goto(`${BASE_URL}/cart`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await this.page.waitForTimeout(1500);
      const data = await this.page.evaluate(() => {
        const items = [];
        document.querySelectorAll('[class*="CartItem"],[class*="cartItem"]').forEach(el => {
          const name = (el.querySelector('[class*="name"]') || el.querySelector('h4'))?.textContent?.trim();
          const qty = el.querySelector('[class*="count"],[class*="quantity"]')?.textContent?.trim() || '1';
          const price = el.querySelector('[class*="price"]')?.textContent?.trim();
          if (name) items.push({ name, quantity: parseInt(qty) || 1, price });
        });
        const total = document.querySelector('[class*="TotalPayable"],[class*="grandTotal"]')?.textContent?.trim();
        return { items, total };
      });
      const screenshot = await this.takeScreenshot();
      return { success: true, ...data, screenshot };
    } catch (err) {
      return { success: false, error: err.message, items: [] };
    }
  }

  async proceedToCheckout() {
    try {
      for (const sel of ['button:has-text("Proceed to Pay")', 'button:has-text("Place Order")', '[class*="proceedToPay"]']) {
        try {
          const btn = this.page.locator(sel).first();
          if (await btn.isVisible({ timeout: 3000 })) {
            await btn.click(); await this.page.waitForTimeout(2000);
            const screenshot = await this.takeScreenshot();
            return { success: true, screenshot };
          }
        } catch { continue; }
      }
      return { success: false, error: 'Checkout button not found' };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  async takeScreenshot() {
    try {
      const buf = await this.page.screenshot({ type: 'png', fullPage: false });
      return buf.toString('base64');
    } catch { return null; }
  }

  async close() {
    if (this.browser) { await this.browser.close(); }
  }
}

// ── Agent pool ────────────────────────────────────────────────────────────────
const agentPool = new Map();
export const getAgent = (sid) => agentPool.get(sid);

export async function createAgent(sid) {
  if (agentPool.has(sid)) return agentPool.get(sid);
  const agent = new FoodOrderingAgent(sid);
  await agent.init();
  agentPool.set(sid, agent);
  return agent;
}

export async function destroyAgent(sid) {
  const agent = agentPool.get(sid);
  if (agent) { await agent.close(); agentPool.delete(sid); }
}
