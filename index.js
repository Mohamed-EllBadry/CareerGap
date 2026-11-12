
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import md from 'md-2-json'
import crypto from 'node:crypto'

const moduleDirectory = path.dirname(fileURLToPath(import.meta.url))

const roadmapDirectory = path.resolve(
  moduleDirectory,
  '../roadmap.sh/developer-roadmap/roadmaps/',
)

const outputDirectory = path.join(moduleDirectory, 'json')
const outputFile = path.join(outputDirectory, 'skills.json')

let roadMapsNodesCount = new Object()
const skillsMap = new Map()

const start = Date.now()

// Generate unique IDs
function idGenerator() {
  return crypto.randomBytes(32).toString('hex')
}

// Get all files recursively from a directory
function getFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const entryPath = path.join(directory, entry.name)

    if (entry.isDirectory()) {
      return getFiles(entryPath)
    }

    return entry.isFile() && entry.name.endsWith('.md') ? [entryPath] : []
  })
}

// Extract resources from markdown content
function getResources(content) {
  return Array.from(
    content.matchAll(/\[@([^@]+)@([^\]]+)\]\(([^)]+)\)/g),
    ([, type, title, url]) => ({
      type,
      title,
      url,
    }),
  )
}

// Extract skill name from markdown heading
function getSkillName(content) {
  const firstHeading = content.split('\n').find(line => /^#\s+/.test(line))

  if (!firstHeading) return null

  return firstHeading.replace(/^#\s+/, '').trim().toLowerCase()
}

// Extract skill description
function getSkillContent(content, skillName) {
  const parsed = md.parse(content)

  const heading = content
    .split('\n')
    .find(line => /^#\s+/.test(line))
    ?.replace(/^#\s+/, '')
    .trim()

  return parsed[heading]?.raw?.split('\n')[0] ?? ''
}

// Merge differences into the first occurrence of a skill
function mergeSkill(existingSkill, skill_content, track) {
  // Add new skill content only if it doesn't already exist
  if (
    skill_content &&
    !existingSkill.skill_content.includes(skill_content)
  ) {
    existingSkill.skill_content = [
      existingSkill.skill_content,
      skill_content,
    ]
      .filter(Boolean)
      .join('\n')
  }

  // Check if the track already exists
  const existingTrack = existingSkill.tracks.find(
    existing => existing.track_name === track.track_name,
  )

  if (existingTrack) {
    // Merge only new resources into the existing track
    existingTrack.rsc = [
      ...existingTrack.rsc,
      ...track.rsc.filter(
        resource =>
          !existingTrack.rsc.some(
            existing =>
              existing.type === resource.type &&
              existing.title === resource.title &&
              existing.url === resource.url,
          ),
      ),
    ]
  } else {
    // Add the new track
    existingSkill.tracks.push(track)
  }
}

// Generate skills and merge duplicates
function GenerateJsonFromDirFiles(slug) {
  const roadmapFiles = path.resolve(roadmapDirectory, slug)

  // console.log(`\nProcessing roadmap: ${slug}`)
  // console.log(`Directory: ${roadmapFiles}`)

  if (!fs.existsSync(roadmapFiles)) {
    console.error(`Directory does not exist: ${roadmapFiles}`)
    return
  }

  const files = getFiles(roadmapFiles)

  // console.log(`Files found: ${files.length}`)

  // ORIGINAL: No local counter initialization.
  // FIXED: Each track gets its own counter starting at zero.
  // Since track_name is determined below, initialize it after extracting the name.

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8')

    const skill_name = getSkillName(content)

    if (!skill_name) {
      // console.log(`Skipped (no heading): ${file}`)
      continue
    }

    // Track name is extracted from the directory structure
    const relativePath = path.relative(roadmapFiles, file)
    const track_name = slug.split('/')[0]

    const skill_content = getSkillContent(content, skill_name)

    // ORIGINAL (causes NaN):
    // roadMapsNodesCount[`${track_name}`] = 1 + Number(roadMapsNodesCount[`${track_name}`])

    // FIXED: Initialize the track counter at zero if it doesn't exist,
    // then increment it for every skill encountered.
    roadMapsNodesCount[track_name] =
      (roadMapsNodesCount[track_name] ?? 0) + 1

    const track = {
      track_id: idGenerator(),
      track_name,
      // ORIGINAL:
      // skill_count: 0,

      // FIXED: Store the current position in this track.
      skill_count: roadMapsNodesCount[track_name],

      rsc: getResources(content),
    }

    // ORIGINAL (incorrect property access):
    // roadMapsNodesCount.track_name += 1

    // FIXED: No additional increment is needed.
    // The counter was already incremented using the dynamic track_name key.

    console.log({
      track_name,
      cnt: track.skill_count,
      roadmapcount: roadMapsNodesCount[track_name],
    })

    // console.log(`Skill found: ${skill_name}`)

    // Check if the skill already exists
    if (skillsMap.has(skill_name)) {
      const existingSkill = skillsMap.get(skill_name)

      // Merge only the differences into the first skill occurrence
      mergeSkill(existingSkill, skill_content, track)

      // console.log(`Duplicate merged: ${skill_name}`)

      continue
    }

    // Create a new skill
    const skill = {
      skill_id: idGenerator(),
      skill_name,
      skill_content,
      tracks: [track],
    }

    skillsMap.set(skill_name, skill)
  }
}

// Main execution
try {
  // console.log('Starting roadmap processing...')
  // console.log(`Roadmap directory: ${roadmapDirectory}`)

  if (!fs.existsSync(roadmapDirectory)) {
    throw new Error(`Roadmap directory not found: ${roadmapDirectory}`)
  }

  const directories = fs
    .readdirSync(roadmapDirectory, {
      withFileTypes: true,
    })
    .filter(entry => entry.isDirectory())

  // console.log(`Roadmap directories found: ${directories.length}`)

  for (const dir of directories) {
    // ORIGINAL:
    // GenerateJsonFromDirFiles(`${dir.name}/content`)

    // FIXED: Reset counters before processing each new roadmap.
    // This ensures the first skill in every roadmap starts at 1.
    roadMapsNodesCount[dir.name] = 0

    GenerateJsonFromDirFiles(`${dir.name}/content`)
  }

  // Recalculate skill_count after removing duplicates
  const trackSkills = new Map()

  for (const skill of skillsMap.values()) {
    for (const track of skill.tracks) {
      if (!trackSkills.has(track.track_name)) {
        trackSkills.set(track.track_name, [])
      }

      trackSkills.get(track.track_name).push(track)
    }
  }

  // Sort skills by their original position and assign consecutive positions
  for (const tracks of trackSkills.values()) {
    tracks.sort((a, b) => a.skill_count - b.skill_count)

    tracks.forEach((track, index) => {
      track.skill_count = index + 1
    })
  }

  // Convert Map values into an array
  const jsonArray = Array.from(skillsMap.values())

  // Create output directory
  fs.mkdirSync(outputDirectory, { recursive: true })

  // Write JSON file
  fs.writeFileSync(outputFile, JSON.stringify(jsonArray, null, 2), 'utf8')

  // Execution summary
  // console.log('\n========== SUMMARY ==========')

  // console.log({
  //   success: true,
  //   total_skills: jsonArray.length,
  //   total_tracks: jsonArray.reduce(
  //     (total, skill) => total + skill.tracks.length,
  //     0,
  //   ),
  //   output_file: outputFile,
  //   execution_time: `${Date.now() - start}ms`,
  // })

  if (jsonArray.length === 0) {
    console.warn(
      'WARNING: No skills were extracted. Check the directory paths and Markdown heading structure.',
    )
  }
} catch (error) {
  console.error('Error while generating skills:', error)
  process.exitCode = 1
}
