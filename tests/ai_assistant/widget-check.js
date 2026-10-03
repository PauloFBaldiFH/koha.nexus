// Browser check of the AI assistant on the staff home page (tests only):
//   NODE_PATH=$(npm root -g) node widget-check.js BASE_URL [SCREENSHOT.png]
// BASE_URL is a running tests/ai_assistant/staff-mock. Prints "ok <step>"
// lines; any failure exits 1 with the reason.
const { chromium } = require("playwright");
const base = process.argv[2];
const shot = process.argv[3];

function check(cond, what) {
    if (!cond) throw new Error("FAILED: " + what);
    console.log("ok " + what);
}

(async () => {
    const browser = await chromium.launch(process.env.KEI_CHROMIUM ? { executablePath: process.env.KEI_CHROMIUM } : {});
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    try {
        await page.goto(base + "/cgi-bin/koha/mainpage.pl");
        await page.waitForSelector("#kei-ai .kei-ai-log .kei-ai-assistant");
        check(await page.locator("#area-news").count() === 0, "the news block is gone");
        check(await page.locator(".col-md-3 > #kei-ai").count() === 1, "the chat is in the news column");
        check(await page.locator(".col-md-3 > #kei-ai + #area-quote").count() === 1, "in the place of the news, above the quote");
        check(await page.locator("#kei-ai .kei-ai-chip").count() === 0, "no example questions under the chat");

        await page.fill("#kei-ai textarea", "that book about the clown that was made into a movie...");
        await page.press("#kei-ai textarea", "Enter");
        check(await page.locator("#kei-ai .kei-ai-pac").isVisible(), "the Pac-Man loader runs while it thinks");
        await page.waitForSelector("#kei-ai a.kei-ai-link[href*='biblionumber=1']");
        check(await page.locator("#kei-ai .kei-ai-pac").isHidden(), "the loader is hidden after the answer");
        const color = await page.locator("#kei-ai a.kei-ai-link").first().evaluate((a) => getComputedStyle(a).color);
        check(color === "rgb(11, 98, 214)", "record links are blue (" + color + ")");
        const hrefs = await page.locator("#kei-ai a.kei-ai-link").evaluateAll((l) => l.map((a) => a.getAttribute("href")));
        check(hrefs.includes("/cgi-bin/koha/catalogue/detail.pl?biblionumber=2"), "A coisa links to its record");

        await page.fill("#kei-ai textarea", "The last patron with 4 overdue books and 144 in fines");
        await page.press("#kei-ai textarea", "Enter");
        await page.waitForSelector("#kei-ai a.kei-ai-link[href*='borrowernumber=101']");
        check(/4 overdue/.test(await page.locator("#kei-ai .kei-ai-assistant").last().innerText()), "the patron with 4 overdue and 144 in fines");

        await page.fill("#kei-ai textarea", "waive Ana's fines");
        await page.press("#kei-ai textarea", "Enter");
        const card = page.locator("#kei-ai .kei-ai-proposal").last();
        await card.waitFor();
        check(/UPDATE accountlines/.test(await card.locator("pre.kei-ai-sql").innerText()), "the exact SQL is previewed");
        await card.locator("button.btn-warning").click();
        check((await card.locator("button.btn-danger").innerText()).trim() === "Yes, run it", "Confirm asks a second time");
        if (shot) {
            await page.locator("#kei-ai .kei-ai-log").evaluate((l) => { l.scrollTop = l.scrollHeight; });
            await page.screenshot({ path: shot });
            console.log("ok screenshot " + shot);
        }
        await card.locator("button.btn-danger").click();
        await page.waitForSelector("#kei-ai .kei-ai-proposal.kei-ai-done");
        check(/2 rows changed/.test(await page.locator("#kei-ai .kei-ai-proposal.kei-ai-done").innerText()), "the change ran after the second click");

        // A text from the model is never HTML.
        await page.reload();
        await page.waitForSelector("#kei-ai .kei-ai-proposal.kei-ai-done");
        check(await page.locator("#kei-ai .kei-ai-msg").count() === 6, "the conversation is kept across reloads");
        await page.fill("#kei-ai textarea", "<img src=x onerror=alert(1)>");
        await page.press("#kei-ai textarea", "Enter");
        await page.waitForFunction(() => document.querySelectorAll("#kei-ai .kei-ai-msg").length === 8);
        check(await page.locator("#kei-ai img").count() === 0, "typed HTML is shown as text");

        await page.goto(base + "/cgi-bin/koha/mainpage.pl?nonews=1");
        await page.waitForSelector("#kei-ai .kei-ai-log .kei-ai-msg");
        check(await page.locator(".col-md-3 > #kei-ai:first-child").count() === 1, "without news it opens the first column");
        check(errors.length === 0, "no JavaScript errors " + errors.join("; "));
    } catch (e) {
        console.error(e.message);
        await browser.close();
        process.exit(1);
    }
    await browser.close();
})();
