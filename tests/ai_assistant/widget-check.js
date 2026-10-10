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

        // The input: three lines to start, grows with the text up to its
        // limit and then scrolls inside; shrinks back when the text goes.
        const box = () => page.$eval("#kei-ai textarea", (t) => ({ h: t.offsetHeight, max: parseFloat(getComputedStyle(t).maxHeight),
            min: parseFloat(getComputedStyle(t).minHeight), oy: getComputedStyle(t).overflowY, sh: t.scrollHeight, ch: t.clientHeight }));
        const start = await box();
        check(start.h >= start.min && start.h <= start.min + 2, "the input starts at three lines (" + start.h + "px)");
        await page.click("#kei-ai textarea");
        await page.keyboard.type("short question");
        check((await box()).h === start.h, "a short question keeps that height");
        await page.keyboard.type(" and a very long prompt that goes on".repeat(30));
        const long = await box();
        check(long.h <= long.max + 1 && long.h <= 900 / 3 + 1, "a long prompt stops growing at " + long.max + "px (" + long.h + "px)");
        check(long.oy === "auto" && long.sh > long.ch, "and scrolls inside");
        await page.keyboard.type(" more".repeat(40));
        check((await box()).h === long.h, "typing on does not grow it any more");
        await page.click("#kei-ai textarea");
        await page.fill("#kei-ai textarea", "back to one line");
        await page.dispatchEvent("#kei-ai textarea", "input");
        check((await box()).h === start.h, "deleting the text shrinks it back (a click does not pin the height)");
        await page.fill("#kei-ai textarea", "x ".repeat(400));
        await page.dispatchEvent("#kei-ai textarea", "input");
        await page.fill("#kei-ai textarea", "that book about the clown that was made into a movie...");
        await page.press("#kei-ai textarea", "Enter");
        check(await page.locator("#kei-ai .kei-ai-pac").isVisible(), "the Pac-Man loader runs while it thinks");
        await page.waitForSelector("#kei-ai a.kei-ai-link[href*='biblionumber=1']");
        check((await box()).h === start.h, "after sending, the input is back to three lines");
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
        check(/outstanding fines/.test(await card.locator("table.kei-ai-diff").innerText()), "the proposal shows the field");
        check((await card.locator("td.kei-ai-from").innerText()).trim() === "144.00"
              && (await card.locator("td.kei-ai-to").innerText()).trim() === "0.00", "with its value now and after");
        check(/Ana Souza/.test(await card.locator("a.kei-ai-link").innerText()), "and the patron it changes");
        check((await card.locator("button.kei-ai-approve").innerText()).trim() === "Approve & Execute", "an Approve & Execute button");
        check(await card.locator("button.kei-ai-reject").count() === 1, "and a Reject button");
        if (shot) {
            await page.locator("#kei-ai .kei-ai-log").evaluate((l) => { l.scrollTop = l.scrollHeight; });
            await page.screenshot({ path: shot });
            console.log("ok screenshot " + shot);
        }
        await card.locator("button.kei-ai-approve").click();
        await page.waitForSelector("#kei-ai .kei-ai-proposal.kei-ai-done");
        check(/Koha made the change/.test(await page.locator("#kei-ai .kei-ai-proposal.kei-ai-done").innerText()), "the change ran after Approve");

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
