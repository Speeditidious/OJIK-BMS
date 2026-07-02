import assert from "node:assert/strict";

import {
  formatRatingContributionCardRankLabel,
  getDayStatRatingContributionEntries,
  getDisplayedRatingRankData,
} from "./rating-detail-display-core.mjs";

const currentRank = {
  table_slug: "stella",
  status: "ok",
  exp: 1000,
  rating: 5000,
  rating_norm: 10,
  bms_force: 10,
  dan_decoration: {
    dan_title: "st1",
    display_text: "st1",
    color: "#fff",
    glow_intensity: "subtle",
  },
};

const historicalSummary = {
  exp: 100,
  rating: 300,
  rating_norm: 0.6,
  top_n: 100,
};

{
  const displayed = getDisplayedRatingRankData({
    ratingAsOf: "2026-05-01",
    myRank: currentRank,
    contributionData: { summary: historicalSummary },
  });

  assert.equal(displayed.dan_decoration, null);
  assert.equal(displayed.exp, 100);
  assert.equal(displayed.rating, 300);
  assert.equal(displayed.bms_force, 0.6);
}

{
  const displayed = getDisplayedRatingRankData({
    ratingAsOf: "2026-05-01",
    myRank: currentRank,
    contributionData: null,
  });

  assert.equal(displayed.dan_decoration, null);
}

{
  const displayed = getDisplayedRatingRankData({
    ratingAsOf: null,
    myRank: currentRank,
    contributionData: { summary: historicalSummary, dan_decoration: null },
  });

  assert.equal(displayed.dan_decoration, currentRank.dan_decoration);
  assert.equal(displayed.exp, 1000);
}

assert.equal(formatRatingContributionCardRankLabel("MAX-", 17), "MAX-");
assert.equal(formatRatingContributionCardRankLabel("AAA", 17), "AAA");
assert.equal(formatRatingContributionCardRankLabel(null, 17), null);
assert.equal(formatRatingContributionCardRankLabel("MAX-", 0, 9), null);

{
  const visible = getDayStatRatingContributionEntries([
    {
      title: "Low",
      value: 200,
      delta_rating: 10,
      is_in_top_n: true,
      was_in_top_n: true,
    },
    {
      title: "High",
      value: 350,
      delta_rating: 3,
      is_in_top_n: true,
      was_in_top_n: true,
    },
    {
      title: "Entered",
      value: 250,
      delta_rating: 0,
      is_in_top_n: true,
      was_in_top_n: false,
    },
    {
      title: "Dropped",
      value: 500,
      delta_rating: 0,
      is_in_top_n: false,
      was_in_top_n: true,
    },
  ]);

  assert.deepEqual(visible.map((entry) => entry.title), ["High", "Entered", "Low"]);
}

{
  const visible = getDayStatRatingContributionEntries([
    {
      title: "Dropped Only",
      value: 500,
      delta_rating: 0,
      is_in_top_n: false,
      was_in_top_n: true,
    },
  ]);

  assert.deepEqual(visible, []);
}
