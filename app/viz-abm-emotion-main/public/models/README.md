# 3D Models for Agent Visualization

This directory contains the 3D models used for visualizing different types of agents in the simulation.

## Required Models

The following GLB models are required:

1. `foot.glb` - A simple human figure model for walking agents
2. `car.glb` - A basic car model for agents using cars
3. `bicycle.glb` - A bicycle model for agents using bicycles

## Model Requirements

- Format: GLB (binary glTF)
- Scale: Models should be normalized to approximately 1 unit in size
- Orientation: Models should be oriented with their forward direction along the positive X-axis
- Materials: Models should use PBR materials for proper lighting and color application

## Where to Get Models

You can find suitable models from the following sources:

1. [Sketchfab](https://sketchfab.com/) - Many free and paid models available
2. [Google Poly Archive](https://poly.pizza/) - Archive of Google Poly models
3. [TurboSquid](https://www.turbosquid.com/) - Professional 3D models

## Model Placement

Place your GLB models in this directory with the exact filenames specified above. The models will be automatically loaded by the application.

## Model Optimization

For best performance:
- Keep polygon counts reasonable (under 50k triangles per model)
- Use texture atlases where possible
- Optimize materials and textures
- Remove unnecessary metadata and animations 