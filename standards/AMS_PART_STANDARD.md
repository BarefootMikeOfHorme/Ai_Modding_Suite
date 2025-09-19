# AMS Part Standard (Draft)

Purpose
- Define a CAD-like, engine-agnostic part description capable of driving both:
  - “standard texture overlay” parts (simple mesh + materials), and
  - high-definition, physically-detailed parts (multi-mesh, LODs, colliders, attachment nodes, parametric features).
- Preserve scale fidelity (mm/m) and interoperability with Unity/Unreal/KSP-style ecosystems.

Core concepts
- Units & scale
  - SI units (meters), with profile-aware inputs (mm for small parts, meters for normal/scene).
- Geometry
  - Pivot conventions, up/forward axes, handedness rules; explicit transforms per node.
  - Composition of primitives (box, cylinder, capsule, cone, torus, plane) and imported meshes.
  - LOD chain, collision meshes (primitive/UCX), optional convex decomposition hints.
- Materials & textures
  - PBR channels (baseColor, normal, metallic, roughness, AO, emissive) with channel packing options.
  - Per-material pipeline hints (Unity URP/HDRP; Unreal with packed textures; defaults).
- Attachment nodes
  - Named nodes with position (m), orientation (unit vectors), size/radius, and rules (stack/surface/snap).
  - Optional KSP-compliant node definitions and TweakScale hints.
- Parameters
  - Declarative parameters (e.g., diameter, lengthFactor, wallThickness) for parametric parts.
  - Resolved at build time to generate actual meshes; stored in sidecars.
- Metadata & lineage
  - AMS Enhanced Metadata sidecars record creation context, geometry bounds, hashes, tags, iteration, and lineage.

Deliverables
- Geometry: GLB (pivoted and unit-correct), optional FBX for engine-specific flows.
- Sidecars: .ams.json/.ams.yaml with full metadata.
- Engine sidecars: Unity/Unreal import hints (up-axis, unit scale, material mapping).
- (Optional) KSP .cfg template for part config and nodes.

Recommended workflow
1) Author part via preset or recipe (JSON/YAML) with parameters + inputs.
2) Generate GLB + AMS sidecars; inspect extents and metadata in Inspector.
3) Export engine sidecars; import into Unity/Unreal with consistent scale/axes.
4) For KSP: generate .cfg nodes and place colliders per template.

Open items
- Define full JSON schema for AMS Part Standard (parameters, nodes, materials, LODs, colliders, tags).
- Provide importers/exporters for Unity and Unreal via editor scripts or CLI.
- Add validation rules for parameters (ranges, dependency constraints) and node correctness.
