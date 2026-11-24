const { chromium } = require(process.env.MMI_PLAYWRIGHT_MODULE || "playwright");
(async () => {
  let browser = await chromium.launch({
    executablePath: process.env.MMI_BROWSER_EXECUTABLE || undefined,
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--no-zygote",
      "--single-process",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--in-process-gpu",
      "--disable-gpu-sandbox",
    ],
    env: process.env,
  });
  try {
    const page = await browser.newPage({
        viewport: { width: 1512, height: 1100 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(process.env.MMI_TEST_URL + "/");
    await page.waitForSelector("#auth:visible");
    if (await page.locator("#setupKey").isVisible())
      await page.fill("#setupKey", process.env.MMI_TEST_INSTALL_KEY);
    await page.fill("#username", "admin");
    await page.fill("#password", "AdminPassword123");
    await page.click("#authSubmit");
    await page.waitForSelector("#workspace:visible");
    await page.waitForFunction(() =>
      document.querySelector("#liveLabel").textContent.includes("LIVE"),
    );
    for (let [id, value] of Object.entries({
      mobile: "03001234567",
      name: "Hostinger Browser Visitor",
      cnic: "0123456789012",
      host: "HR Manager",
      purpose: "Web visit",
      remarks: "Saved through PHP",
    }))
      await page.fill("#" + id, value);
    await page.click("#save");
    await page.waitForSelector("#rows .out-button");
    await page.click("#rows .out-button");
    await page.waitForFunction(() =>
      document.querySelector("#rows").textContent.includes("Completed"),
    );
    await page.fill("#mobile", "0");
    await page.waitForSelector("#matches .match");
    await page.click("#matches .match");
    if ((await page.inputValue("#name")) !== "Hostinger Browser Visitor")
      throw Error("Visitor autofill failed");
    await page.fill("#remarks", "Repeat visit");
    await page.click("#save");
    await page.waitForFunction(
      () => document.querySelector("#inside").textContent === "1",
    );
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({
      path: "/tmp/mmi-hostinger-visitor.png",
      fullPage: true,
    });
    const popupP = page.waitForEvent("popup");
    await page.click("#printHistory");
    const popup = await popupP;
    await popup.waitForLoadState();
    if (
      !(await popup.locator("body").innerText()).includes(
        "Hostinger Browser Visitor",
      )
    )
      throw Error("PHP print report failed");
    await popup.close();
    await page.click("#tabCalls");
    await page.fill("#callPhone", "0");
    await page.waitForSelector("#callMatches .match");
    await page.click("#callMatches .match");
    await page.click("#startCall");
    await page.waitForTimeout(1000);
    await page.click("#endCall");
    await page.fill("#callRemarks", "Callback through PHP");
    await page.click("#callSave");
    await page.waitForFunction(() =>
      document
        .querySelector("#callRows")
        .textContent.includes("Callback through PHP"),
    );
    await page.locator("#callRows button").filter({ hasText: "Edit" }).click();
    await page.fill("#callRemarks", "PHP correction saved");
    await page.fill("#callReason", "Follow-up details");
    await page.click("#callSave");
    await page.waitForFunction(() =>
      document
        .querySelector("#callRows")
        .textContent.includes("PHP correction saved"),
    );
    await page.fill("#callSearch", "Hostinger");
    await page.waitForFunction(() =>
      document.querySelector("#callPageLabel").textContent.includes("1 calls"),
    );
    const downloadP = page.waitForEvent("download");
    await page.click("#exportCalls");
    const dl = await downloadP;
    if (!dl.suggestedFilename().endsWith(".csv"))
      throw Error("Call CSV not downloadable");
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({
      path: "/tmp/mmi-hostinger-calls.png",
      fullPage: true,
    });
    await page.click("#tabAdmin");
    await page.fill("#userId", "reception");
    await page.fill("#userName", "Reception Team");
    await page.fill("#userPassword", "ReceptionPass123");
    await page.click("#userSave");
    await page.waitForFunction(() =>
      document.querySelector("#users").textContent.includes("reception"),
    );
    await page.click("#logout");
    await page.fill("#username", "reception");
    await page.fill("#password", "ReceptionPass123");
    await page.click("#authSubmit");
    await page.waitForSelector("#workspace:visible");
    if (await page.locator("#tabAdmin").isVisible())
      throw Error("Admin UI exposed to staff");
    await page.setViewportSize({ width: 390, height: 844 });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Mobile overflow");
    await page.screenshot({
      path: "/tmp/mmi-hostinger-mobile.png",
      fullPage: true,
    });
    if (errors.length) throw Error(errors.join("; "));
    console.log(
      "Chromium PHP/MySQL PASS: login, IN/OUT, prefix autofill, repeat visit, visitor print, call timer/save/edit/search/CSV, admin account, staff login and mobile viewport; no JS errors.",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
