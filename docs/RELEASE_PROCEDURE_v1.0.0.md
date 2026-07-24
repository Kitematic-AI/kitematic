# Release Procedure — v1.0.0

## Prerequisites

Before creating the v1.0.0 tag, confirm:

- [ ] RC Validation workflow passed on fresh CI runner
- [ ] 24-hour staging run completed with all exit criteria met
- [ ] API freeze review signed off
- [ ] Dependency health check passed
- [ ] All quality gates green locally

## Step 1: Final RC Validation (CI)

Trigger the RC Validation workflow:

```bash
gh workflow run rc-validation.yml --ref main
```

Monitor results at: https://github.com/kitematic/kitematic/actions

## Step 2: Staging Deployment

```bash
# Deploy the RC image to staging
kubectl set image deployment/kitematic-api kitematic-api=ghcr.io/kitematic/kitematic-api:1.0.0-rc.1

# Monitor for 24 hours
kubectl logs -l app=kitematic --tail=50 -f

# Verify exit criteria (see docs/05_DEPLOYMENT/STAGING_VALIDATION.md)
```

## Step 3: Create Git Tag

```bash
# Create annotated tag
git tag -a v1.0.0 -m "v1.0.0 — First stable release"

# Push tag to origin
git push origin v1.0.0
```

## Step 4: Generate Release Artifacts

```bash
# Generate SBOM
cyclonedx-py > sbom.json

# Generate checksums
sha256sum sbom.json > checksums.txt
sha256sum CHANGELOG.md >> checksums.txt

# Get Docker image digest
docker inspect --format='{{index .RepoDigests 0}}' kitematic-api:v1.0.0
```

## Step 5: Create GitHub Release

Using `gh` CLI:

```bash
gh release create v1.0.0 \
  --title "v1.0.0 — First Stable Release" \
  --notes-file docs/RELEASE_NOTES_v1.0.0.md \
  --discussion-category "announcements" \
  sbom.json \
  checksums.txt
```

Or via GitHub UI:
1. Go to https://github.com/kitematic/kitematic/releases/new
2. Tag: `v1.0.0`
3. Title: `v1.0.0 — First Stable Release`
4. Description: Paste contents of `docs/RELEASE_NOTES_v1.0.0.md`
5. Attach: `sbom.json`, `checksums.txt`
6. Publish release

## Step 6: Post-Release Verification

```bash
# Verify tag exists
git tag -l 'v1.0.0'

# Verify release was created
gh release view v1.0.0

# Verify Docker image
docker pull ghcr.io/kitematic/kitematic-api:v1.0.0

# Verify health check
curl https://api.kitematic.dev/api/v1/health
```

## Step 7: Create Release Branch

```bash
git checkout -b v1.0.x v1.0.0
git push origin v1.0.x
```

This branch is for critical bug fixes and security patches only. No new features.

## Step 8: Open Next Milestone

Create a new milestone for `v1.1.0` in the GitHub project.
See [ROADMAP.md](ROADMAP.md) for planned work items.

## Step 9: Announce

- GitHub Discussion
- Slack #announcements
- Email to stakeholders (if applicable)

## Rollback (if issues found post-release)

```bash
# Create hotfix branch from tag
git checkout -b hotfix/v1.0.1 v1.0.0

# Fix issue, bump version to 1.0.1
git commit -m "fix: ..."
git tag -a v1.0.1 -m "v1.0.1 — Hotfix"
git push origin v1.0.1
```
