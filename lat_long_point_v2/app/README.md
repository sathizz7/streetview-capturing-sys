# Building Capture System - Streamlit UI

## Overview
Interactive web interface for the Building Detection V2 Pipeline with Folium map integration.

## Installation

1. **Install Streamlit dependencies:**
```bash
cd lat_long_point_v2/app
pip install -r requirements.txt
```

2. **Verify backend dependencies are installed:**
```bash
cd ..
pip install -r requirements.txt
```

## Running the Application

```bash
cd lat_long_point_v2
streamlit run app/streamlit_app.py
```

The app will open in your default browser at `http://localhost:8501`

## Features

### 📍 Interactive Map
- OpenStreetMap base layer via Folium
- GeoJSON building polygon visualization
- Click-to-select functionality (50m radius detection)
- Visual markers and tooltips with building metadata

### 📁 Data Management
- **Upload New GeoJSON**: Upload `.geojson` or `.json` files
- **Load Existing Data**: Select from files in `app/data/buildings/`
- **Manual JSON Input**: Paste GeoJSON directly with real-time validation

### 🚀 Pipeline Integration
- Run full building analysis pipeline
- Progress tracking
- Supports polygon-based frontage validation

### 📸 Results Display
- Street View image gallery
- Building analysis insights
- Metadata for each capture

### 💾 Export
- **Enhanced GeoJSON**: Original building data + analysis results + image URLs
- **Image URLs (TXT)**: Simple list of image URLs for easy access

## Usage

1. **Load Building Data**:
   - Upload a GeoJSON file, or
   - Select from existing files, or
   - Paste JSON manually

2. **Select Building**:
   - Click on a building polygon on the map
   - Selected building info appears in sidebar

3. **Run Analysis**:
   - Click "🚀 Run Analysis" button
   - Wait for pipeline to complete (10-30 seconds)

4. **View Results**:
   - Browse Street View images
   - Read building analysis
   - Download enhanced GeoJSON or image URLs

## GeoJSON Format

### Required Structure
```json
{
  "type": "Feature",
  "properties": {
    "latitude": 17.408,
    "longitude": 78.451,
    "area_in_me": 250,      // optional
    "confidence": 0.95       // optional
  },
  "geometry": {
    "type": "Polygon",      // or "MultiPolygon"
    "coordinates": [...]
  }
}
```

- **latitude/longitude** can be in properties OR computed from geometry
- Supports both `Polygon` and `MultiPolygon` geometries
- Can be a single `Feature` or `FeatureCollection`

### Output Format

Enhanced GeoJSON includes:
```json
{
  "properties": {
    ...
    "pipeline_results": {
      "status": "success",
      "execution_time": 12.3,
      "image_urls": [
        "https://maps.googleapis.com/...",
        "https://maps.googleapis.com/..."
      ],
      "analysis": {
        "building_usage_summary": "Commercial",
        "visual_description": "...",
        "establishments": [...]
      }
    }
  }
}
```

## Directory Structure

```
app/
├── streamlit_app.py          # Main application
├── requirements.txt          # Streamlit dependencies
├── components/
│   ├── map_viewer.py         # Folium map component
│   ├── json_validator.py    # JSON validation
│   ├── pipeline_runner.py   # Pipeline integration
│   └── results_display.py   # Results visualization
├── utils/
│   ├── coordinates.py        # Spatial calculations
│   └── geojson_helpers.py   # GeoJSON utilities
└── data/
    └── buildings/            # Stored GeoJSON files
```

## Troubleshooting

### Import Errors
If you see import errors, ensure you're running from the `lat_long_point_v2` directory:
```bash
cd lat_long_point_v2
streamlit run app/streamlit_app.py
```

### Map Not Displaying
- Check that `streamlit-folium` is installed
- Try refreshing the browser

### Pipeline Errors
- Verify `.env` file has `GOOGLE_API_KEY`
- Check API quota/billing status
- Review error messages in UI

## API Key Setup

The pipeline requires a Google Maps API Key. Ensure it's configured in:
```
lat_long_point_v2/.env
```

```env
GOOGLE_API_KEY=your_api_key_here
```
