export type ExternalHashType = "md5" | "sha256";

export interface FumenExternalLink {
  name: string;
  href?: string;
  missingHashType?: ExternalHashType;
  color?: string;
  textColor?: string;
}

export interface FumenExternalLinkGroup {
  labelKey: "fumen.detail.viewer" | "fumen.detail.ir";
  links: FumenExternalLink[];
}

function linkOrMissing(
  name: string,
  hashType: ExternalHashType,
  hash: string | null | undefined,
  href: string,
  style?: Pick<FumenExternalLink, "color" | "textColor">,
): FumenExternalLink {
  return hash ? { name, href, ...style } : { name, missingHashType: hashType, ...style };
}

export function buildFumenExternalLinkGroups(fumen: {
  md5?: string | null;
  sha256?: string | null;
}): FumenExternalLinkGroup[] {
  const md5 = fumen.md5 ?? null;
  const sha256 = fumen.sha256 ?? null;

  return [
    {
      labelKey: "fumen.detail.viewer",
      links: [
        linkOrMissing("ScoreViewer", "md5", md5, `https://bms-score-viewer.pages.dev/view?md5=${md5}`, { color: "#4e7fa8" }),
        linkOrMissing("EZ2PATTERN", "sha256", sha256, `https://ez2pattern.kr/bms/chart?sha256=${sha256}`, { color: "#375a7f" }),
      ],
    },
    {
      labelKey: "fumen.detail.ir",
      links: [
        linkOrMissing("BMS-IR", "md5", md5, `https://www.bms-ir.org/new/song?songmd5=${md5}&view=both`, { color: "#3d5a80", textColor: "#e0eaf5" }),
        linkOrMissing("STELLAVERSE-IR", "md5", md5, `https://ir.stellabms.xyz/charts/${md5}`, { color: "#666699" }),
        linkOrMissing("MinIR", "sha256", sha256, `https://www.gaftalk.com/minir/#/viewer/song/${sha256}/0`, { color: "#40c0c9", textColor: "#ffffff" }),
        linkOrMissing("Mocha", "sha256", sha256, `https://mocha-repository.info/song.php?sha256=${sha256}`, { color: "#a07850" }),
      ],
    },
  ];
}
