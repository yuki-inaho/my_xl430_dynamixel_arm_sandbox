# Chili3D viewing lessons

Use this reference for a local Chili3D manual capture. The following lessons were observed with v0.7.0-beta; inspect the actual local version before accessing its app state. They are presentation techniques, not changes to CAD geometry.

- `view-gizmo.cameraController.view.document.modelManager.rootNode` contains nested nodes. In this version `children()` is a method. Traverse leaves and read names; do not interpret `Array.from(node.children)` as an inventory.
- Capture front/oblique/reverse views against a fixed coordinate contract. U/D/L/R names belong to the model, not to the screen. Measure where each relevant part actually projects before labeling it.
- A camera `lookAt()` changes camera state but may not update matrices/rendering immediately. Update camera matrices before calculating projected callout positions, request a view redraw, then capture the resulting frame.
- A screen-space projection does not prove visibility. A callout to a hidden back screw can land on the front jaw surface. Show the opposite side or explicitly name an intentionally hidden feature; inspect the final screenshot.
- For a bolt, point to its head or opening, rather than the bounding-box center halfway down its hidden shank. Derive the head axis and thickness from the actual model; do not universally assume +Y or 2 mm.
- When emphasizing newly added surfaces, preserve edge materials. Three.js line objects may also have `isMesh`; indiscriminately recoloring every such object can remove the visible boundary between parts. Save original view materials and restore them when finishing.
- Hidden motor/frame views may explain nut positions but do not prove a hand or tool can reach them during assembly. Mark those exclusions in the caption.
