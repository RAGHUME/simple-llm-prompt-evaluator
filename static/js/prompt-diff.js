/**
 * Word-level prompt diff for original vs optimized (LCS on tokens).
 * No dependencies; safe HTML via escapeHtml.
 */
(function (global) {
    'use strict';

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /** Split keeping whitespace chunks so spacing is preserved in diff. */
    function tokenize(s) {
        if (!s) return [];
        var parts = String(s).split(/(\s+)/);
        return parts.filter(function (p) { return p.length > 0; });
    }

    /**
     * @returns {{ leftHtml: string, rightHtml: string }}
     */
    function buildWordDiffHtml(oldStr, newStr) {
        var a = tokenize(oldStr);
        var b = tokenize(newStr);
        var n = a.length;
        var m = b.length;
        var dp = [];
        var i, j;
        for (i = 0; i <= n; i++) {
            dp[i] = new Array(m + 1).fill(0);
        }
        for (i = 1; i <= n; i++) {
            for (j = 1; j <= m; j++) {
                dp[i][j] = a[i - 1] === b[j - 1]
                    ? dp[i - 1][j - 1] + 1
                    : Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
        }
        var leftChunks = [];
        var rightChunks = [];
        i = n;
        j = m;
        while (i > 0 || j > 0) {
            if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
                var eq = '<span class="diff-eq">' + escapeHtml(a[i - 1]) + '</span>';
                leftChunks.unshift(eq);
                rightChunks.unshift(eq);
                i--;
                j--;
            } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
                rightChunks.unshift('<span class="diff-add">' + escapeHtml(b[j - 1]) + '</span>');
                j--;
            } else {
                leftChunks.unshift('<span class="diff-del">' + escapeHtml(a[i - 1]) + '</span>');
                i--;
            }
        }
        return { leftHtml: leftChunks.join(''), rightHtml: rightChunks.join('') };
    }

    /**
     * Full side-by-side diff panel HTML.
     * @param {string} subtitle - optional line under title (e.g. "Dataset row #3")
     */
    function promptDiffPanelHtml(original, optimized, originalScore, improvedScore, subtitle) {
        var d = buildWordDiffHtml(original || '', optimized || '');
        var os = Number(originalScore);
        var ns = Number(improvedScore);
        if (isNaN(os)) os = 0;
        if (isNaN(ns)) ns = 0;
        var delta = ns - os;
        var deltaStr = (delta >= 0 ? '+' : '') + delta.toFixed(1);
        var deltaClass = delta > 0 ? 'diff-delta-pos' : delta < 0 ? 'diff-delta-neg' : 'diff-delta-zero';
        var sub = subtitle
            ? '<div class="prompt-diff-sub">' + escapeHtml(subtitle) + '</div>'
            : '';
        return (
            '<div class="prompt-diff-wrap">' +
            sub +
            '<div class="prompt-diff-scorebar">' +
            '<span class="prompt-diff-ver">v1</span>' +
            '<span class="prompt-diff-score-old">' + os.toFixed(1) + '</span>' +
            '<span class="prompt-diff-arrow">→</span>' +
            '<span class="prompt-diff-ver">v2</span>' +
            '<span class="prompt-diff-score-new">' + ns.toFixed(1) + '</span>' +
            '<span class="prompt-diff-delta ' + deltaClass + '">Δ ' + deltaStr + '</span>' +
            '</div>' +
            '<div class="prompt-diff-grid">' +
            '<div class="prompt-diff-pane">' +
            '<div class="prompt-diff-pane-title">Original prompt</div>' +
            '<div class="prompt-diff-body">' + d.leftHtml + '</div>' +
            '</div>' +
            '<div class="prompt-diff-pane">' +
            '<div class="prompt-diff-pane-title">Optimized prompt</div>' +
            '<div class="prompt-diff-body">' + d.rightHtml + '</div>' +
            '</div>' +
            '</div>' +
            '<div class="prompt-diff-legend">' +
            '<span><span class="diff-legend-swatch diff-del">&nbsp;</span> Removed</span>' +
            '<span><span class="diff-legend-swatch diff-add">&nbsp;</span> Added</span>' +
            '<span><span class="diff-legend-swatch diff-eq">&nbsp;</span> Unchanged</span>' +
            '</div>' +
            '</div>'
        );
    }

    global.PromptDiff = {
        escapeHtml: escapeHtml,
        buildWordDiffHtml: buildWordDiffHtml,
        promptDiffPanelHtml: promptDiffPanelHtml,
    };
})(typeof window !== 'undefined' ? window : this);
