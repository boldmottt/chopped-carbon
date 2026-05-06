// Forged Carbon vectorize - Illustrator menu script
// Pairs with the Python tool installed by install.sh at ~/.forge_carbon/
//
// Usage: File > Scripts > Other Script... -> select this file
// Or copy to /Applications/Adobe Illustrator */Presets.localized/*/Scripts/

#target illustrator

(function () {
    var INSTALL = "~/.forge_carbon";

    // ---------- 1. pick image ----------
    var inputFile = File.openDialog(
        "포지드 카본 스캔 이미지 선택",
        "Image:*.jpg;*.jpeg;*.png;*.tif;*.tiff"
    );
    if (!inputFile) return;

    // ---------- 2. parameter dialog ----------
    var dlg = new Window("dialog", "Forged Carbon Vectorize");
    dlg.orientation = "column";
    dlg.alignChildren = "fill";
    dlg.margins = 16;
    dlg.spacing = 10;

    function row(parent, label, def) {
        var g = parent.add("group");
        g.alignment = "fill";
        var lbl = g.add("statictext", undefined, label);
        lbl.preferredSize.width = 180;
        var et = g.add("edittext", undefined, String(def));
        et.preferredSize.width = 80;
        return et;
    }

    var p1 = dlg.add("panel", undefined, "Resolution & density");
    p1.alignChildren = "fill";
    p1.margins = 12;
    var maxDim = row(p1, "최대 변 길이 (px)", "3000");
    var spacing = row(p1, "섬유 간격 (px)", "5");
    var stroke = row(p1, "라인 두께 (px)", "0.5");

    var p2 = dlg.add("panel", undefined, "Tone");
    p2.alignChildren = "fill";
    p2.margins = 12;
    var fiberLo = row(p2, "섬유 최소 명도 (0-255)", "150");
    var fiberHi = row(p2, "섬유 최대 명도 (0-255)", "250");
    var bg = row(p2, "배경 명도 (0-255)", "6");

    var p3 = dlg.add("panel", undefined, "Options");
    p3.alignChildren = "left";
    p3.margins = 12;
    var chipFills = p3.add("checkbox", undefined, "칩 채움 그리기");
    chipFills.value = true;
    var clahe = p3.add("checkbox", undefined, "CLAHE 적용 (대비 강화)");
    clahe.value = true;
    var openResult = p3.add("checkbox", undefined, "완료 후 새 도큐먼트로 열기");
    openResult.value = true;

    var btns = dlg.add("group");
    btns.alignment = "right";
    btns.add("button", undefined, "취소", { name: "cancel" });
    btns.add("button", undefined, "생성", { name: "ok" });

    if (dlg.show() != 1) return;

    // ---------- 3. paths ----------
    var outDir = inputFile.parent.fsName;
    var baseName = inputFile.name.replace(/\.[^.]+$/, "");
    var outPath = outDir + "/" + baseName + "_forged.svg";
    var outFile = new File(outPath);
    var logPath = "/tmp/forged_carbon.log";

    // ---------- 4. command ----------
    var py = INSTALL + "/.venv/bin/python";
    var script = INSTALL + "/forge_vectorize.py";

    function shq(s) {
        return "'" + String(s).replace(/'/g, "'\\''") + "'";
    }

    var parts = [
        shq(py), shq(script),
        shq(inputFile.fsName),
        "-o", shq(outPath),
        "--max-dim", maxDim.text,
        "--spacing", spacing.text,
        "--stroke-width", stroke.text,
        "--fiber-lo", fiberLo.text,
        "--fiber-hi", fiberHi.text,
        "--bg", bg.text
    ];
    if (chipFills.value) parts.push("--draw-chip-fills");
    if (clahe.value) parts.push("--clahe");

    var inner = parts.join(" ") + " > " + shq(logPath) + " 2>&1";
    var fullCmd = "/bin/bash -lc " + shq(inner);

    // ---------- 5. run ----------
    var t0 = (new Date()).getTime();
    system.callSystem(fullCmd);
    var elapsed = (((new Date()).getTime() - t0) / 1000).toFixed(1);

    // ---------- 6. result ----------
    if (outFile.exists) {
        if (openResult.value) {
            try { app.open(outFile); }
            catch (e) { alert("SVG 생성 OK 이지만 자동 열기 실패:\n" + e); }
        }
        alert("완료 (" + elapsed + "초)\n\n" + outPath);
    } else {
        var log = "";
        var lf = new File(logPath);
        if (lf.exists) {
            lf.encoding = "UTF-8";
            lf.open("r");
            log = lf.read();
            lf.close();
        }
        var tail = log.length > 1200 ? log.substring(log.length - 1200) : log;
        alert(
            "생성 실패. (" + elapsed + "초)\n\n"
            + "Python 도구가 설치돼 있나요?  ~/.forge_carbon/install.sh 를 한 번 실행했는지 확인.\n\n"
            + "로그 (말미):\n" + tail
        );
    }
})();
