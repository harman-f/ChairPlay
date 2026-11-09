# Reviewed, SHA-guarded small fixes for active CarPlay cluster URL runtime behavior.
# Applies ONLY to the transient clone of fd7a22fa1f503695309ec9efad0e48b2d900349f. Never stores MFi material.
param([Parameter(Mandatory=$true)][string]$Checkout)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $Checkout).Path
$operations = @(
  @{
    Path = 'src/main/kotlin/io/github/numberonebot/chairplay/AppProfiles.kt'
    Sha = '6f9fb6088209b0ae01ed4062b8b6621702752e87'
    Replaces = @(
      @{
        Before = @'
        if (text != null && id == active) altView.carViews.profile = runCatching { store.load(id) }.getOrNull()
'@
        After = @'
        if (text != null && id == active) {
            runCatching { store.load(id) }.getOrNull()?.let(altView::profileSaved)
        }
'@
      }
    )
  }
  @{
    Path = 'src/main/kotlin/io/github/numberonebot/chairplay/AltscreenView.kt'
    Sha = 'a86fb03f9d441e8773c4223358ee4ed17205f920'
    Replaces = @(
      @{
        Before = @'
import io.github.numberonebot.chairplay.config.AltscreenContent
'@
        After = @'
import io.github.numberonebot.chairplay.config.AltscreenContent
import io.github.numberonebot.chairplay.config.ClusterProfile
'@
      }
      @{
        Before = @'
    /** A closed AltScreen is not drawn on the iPhone, and asked for again as it opens; none once the app closes. */
'@
        After = @'
    /**
     * A live edit of the active profile changes the current view URL on the existing iPhone connection.
     * Schedule this with other control-plane sends; geometry/zoomFactor remain negotiated until reconnect.
     */
    fun profileSaved(updated: ClusterProfile) {
        touchSender.execute {
            carViews.profile = updated
            show(active())
        }
    }

    /** A closed AltScreen is not drawn on the iPhone, and asked for again as it opens; none once the app closes. */
'@
      }
    )
  }
  @{
    Path = 'src/test/kotlin/io/github/numberonebot/chairplay/session/AltscreenUiTest.kt'
    Sha = 'feb3fe5cf12724543fc9bda6a26ffb25ad7e1b02'
    Replaces = @(
      @{
        Before = @'
    // Each new AltScreen stream starts with the iPhone drawing its initial view, so a stop is sent anew; another
'@
        After = @'
    // A live navigation option edits the cluster URL without reconnecting the underlying video session.
    @Test
    fun `a changed cluster URL is delivered during the same stream`() {
        ui.tell(phone, "maps:/car/instrumentcluster/map", seen = true)
        ui.tell(phone, "maps:/car/instrumentcluster/map?showCompass=yes", seen = true)

        assertEquals(
            listOf(
                "showUI maps:/car/instrumentcluster/map",
                "showUI maps:/car/instrumentcluster/map?showCompass=yes",
            ),
            phone.commands,
        )
    }

    // Each new AltScreen stream starts with the iPhone drawing its initial view, so a stop is sent anew; another
'@
      }
    )
  }
  @{
    Path = 'webui/src/pages/CarProfile.tsx'
    Sha = 'def2d5804dd7f0be85afef4f6cf63132bc12103b'
    Replaces = @(
      @{
        Before = @'
import { useCallback, useEffect, useState } from 'react'
'@
        After = @'
import { useCallback, useEffect, useRef, useState } from 'react'
'@
      }
      @{
        Before = @'
  const [copyName, setCopyName] = useState('')
  const chosen = settings.value('altscreen.profile')
'@
        After = @'
  const [copyName, setCopyName] = useState('')
  const pendingLive = useRef<Promise<void>>(Promise.resolve())
  const chosen = settings.value('altscreen.profile')
'@
      }
      @{
        Before = @'
  function change(next: Profile) {
    setDraft(next)
    setText(JSON.stringify(next, null, 2))
    setDone(null)
  }

  async function save(id: string, saved: string | null) {
    setDone(null)
'@
        After = @'
  function change(next: Profile, live = false) {
    setDraft(next)
    const nextText = JSON.stringify(next, null, 2)
    setText(nextText)
    setDone(null)
    // URL-only view options apply immediately for the selected active profile.
    // Serialize writes so two rapid switches cannot land out of order.
    if (live && editing && editing === chosen) {
      const id = editing
      pendingLive.current = pendingLive.current.catch(() => {}).then(async () => {
        try {
          const error = await backend.saveClusterProfile(id, nextText)
          if (error) setProblem(error)
          else {
            setProblem(null)
            setDone('Saved active view: live iPhone URL requested')
          }
        } catch (error) {
          setProblem(`Live profile update failed: ${String(error)}`)
        }
      })
    }
  }

  async function save(id: string, saved: string | null) {
    await pendingLive.current
    setDone(null)
'@
      }
      @{
        Before = @'
              {draft.views[view] && <ProfileViewForm profile={draft} index={view} change={change} />}
'@
        After = @'
              {draft.views[view] && (
                <>
                  <ProfileViewForm profile={draft} index={view} change={change} liveChange={(next) => change(next, true)} />
                  <Row>
                    <small>Scene, ETA, speed limit, compass and turn card apply immediately when editing the active profile. Navigation apps may ignore unsupported requests. Frame, safe area and native scale still require reconnect.</small>
                  </Row>
                </>
              )}
'@
      }
    )
  }
  @{
    Path = 'webui/src/pages/ProfileViewForm.tsx'
    Sha = 'c1f163bda4cadee725f5fe62e669d780c1acc355'
    Replaces = @(
      @{
        Before = @'
export function ProfileViewForm({ profile, index, change }: { profile: Profile; index: number; change: (p: Profile) => void }) {
'@
        After = @'
export function ProfileViewForm({ profile, index, change, liveChange }: { profile: Profile; index: number; change: (p: Profile) => void; liveChange: (p: Profile) => void }) {
'@
      }
      @{
        Before = @'
onChange={(v) => change(setOption(profile, index, key, v))}
'@
        After = @'
onChange={(v) => liveChange(setOption(profile, index, key, v))}
'@
      }
      @{
        Before = @'
onChange={(v) => change(setViewField(profile, index, 'scene', v))}
'@
        After = @'
onChange={(v) => liveChange(setViewField(profile, index, 'scene', v))}
'@
      }
    )
  }
  @{
    Path = 'webui/src/pages/CarProfile.test.tsx'
    Sha = 'ab5041682579395be01d1f8eb0602a172fdb70e7'
    Replaces = @(
      @{
        Before = @'
    await waitFor(() => expect(backend.profileSaves).toHaveLength(1))
    const saved = JSON.parse(backend.profileSaves[0].text!)
    expect(backend.profileSaves[0].id).toBe('car')
'@
        After = @'
    await waitFor(() => expect(backend.profileSaves).toHaveLength(2))
    const saved = JSON.parse(backend.profileSaves[1].text!)
    expect(backend.profileSaves[1].id).toBe('car')
'@
      }
      @{
        Before = @'
  // Saved, the editor stays on the view being edited rather than going back to the first.
'@
        After = @'
  it('applies navigation URL controls immediately for the active profile, not for other profiles', async () => {
    const backend = await altscreenPage()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Compass' })).getByRole('radio', { name: 'Show' }))

    await waitFor(() => expect(backend.profileSaves).toHaveLength(1))
    const applied = JSON.parse(backend.profileSaves[0].text!)
    expect(applied.views[0].options.showCompass).toBe('yes')

    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Edit' })).getByRole('radio', { name: 'other' }))
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'ETA' })).getByRole('radio', { name: 'Hide' }))
    expect(backend.profileSaves).toHaveLength(1)
  })

  // Saved, the editor stays on the view being edited rather than going back to the first.
'@
      }
    )
  }
)
$pending = @()
foreach ($operation in $operations) {
    $file = Join-Path $root ($operation.Path.Replace('/', [IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing upstream file: $($operation.Path)" }
    $hash = (& git -C $root hash-object -- $file).Trim()
    if ($LASTEXITCODE -ne 0 -or $hash -ne $operation.Sha) {
        throw "Unexpected upstream drift: $($operation.Path), got $hash, expected $($operation.Sha)"
    }
    $content = [System.IO.File]::ReadAllText($file).Replace("`r`n", "`n")
    $changeIndex = 0
    foreach ($replace in $operation.Replaces) {
        # PowerShell here-strings include a trailing newline in some runtimes.
        # The source snippets themselves intentionally have no terminal line break.
        $before = ([string]$replace.Before).Replace("`r`n", "`n").Trim([char[]]@([char]13, [char]10))
        $after = ([string]$replace.After).Replace("`r`n", "`n").Trim([char[]]@([char]13, [char]10))
        $index = $content.IndexOf($before, [StringComparison]::Ordinal)
        $last = $content.LastIndexOf($before, [StringComparison]::Ordinal)
        if ($index -lt 0 -or $index -ne $last) {
            throw "Patch not uniquely applicable to $($operation.Path) change=$changeIndex first=$index last=$last bytes=$($before.Length)"
        }
        $content = $content.Replace($before, $after)
        $changeIndex += 1
    }
    $pending += @{ Path = $file; Text = $content; Name = $operation.Path }
}
foreach ($entry in $pending) {
    [System.IO.File]::WriteAllText($entry.Path, $entry.Text, [System.Text.UTF8Encoding]::new($false))
    Write-Host "LIVE_PROFILE_PATCH_OK $($entry.Name)"
}
Write-Host "LIVE_PROFILE_PATCH=PASS files=$($pending.Count)"
