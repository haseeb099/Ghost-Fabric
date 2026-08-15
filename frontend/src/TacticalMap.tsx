import { useEffect, useMemo, useRef, useState } from 'react'
import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource, Map as MapLibreMap, Marker } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

type MapNode = {
  id: string
  callsign: string
  role: string
  latitude: number
  longitude: number
  status: 'online' | 'degraded' | 'offline'
  is_coordinator: boolean
  latency_ms: number
  links: string[]
}

type Weather = {
  temperature: number
  windSpeed: number
  windDirection: number
  cloudCover: number
  observedAt: string
}

type Props = {
  nodes: MapNode[]
  routes: Record<string, string[]>
}

// Generalized exercise center only; overlay coordinates do not represent real assets.
const MAP_CENTER: [number, number] = [31.2, 49.2]

function buildGeoJson(nodes: MapNode[], routes: Record<string, string[]>) {
  const routedEdges = new Set(
    Object.values(routes).flatMap((route) =>
      route.slice(1).map((nodeId, index) => [route[index], nodeId].sort().join(':')),
    ),
  )
  const nodeFeatures: Feature<Point>[] = nodes.map((node) => ({
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [node.longitude, node.latitude],
    },
    properties: {
      id: node.id,
      status: node.status,
      coordinator: node.is_coordinator,
    },
  }))

  const seen = new Set<string>()
  const linkFeatures: Feature<LineString>[] = []
  nodes.forEach((node) => {
    node.links.forEach((targetId) => {
      const target = nodes.find((item) => item.id === targetId)
      const key = [node.id, targetId].sort().join(':')
      if (!target || seen.has(key)) return
      seen.add(key)
      linkFeatures.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: [
            [node.longitude, node.latitude],
            [target.longitude, target.latitude],
          ],
        },
        properties: {
          failed: node.status === 'offline' || target.status === 'offline',
          routed: routedEdges.has(key),
        },
      })
    })
  })

  return {
    nodes: { type: 'FeatureCollection', features: nodeFeatures } as FeatureCollection,
    links: { type: 'FeatureCollection', features: linkFeatures } as FeatureCollection,
  }
}

function syncMarkers(map: MapLibreMap, nodes: MapNode[], markers: Marker[]) {
  markers.forEach((marker) => marker.remove())
  return nodes.map((node) => {
    const element = document.createElement('div')
    const handoff = node.is_coordinator && node.status === 'degraded'
    element.className = [
      'geo-node-label',
      node.status,
      node.is_coordinator ? 'coordinator' : '',
      handoff ? 'handoff' : '',
    ]
      .filter(Boolean)
      .join(' ')
    element.setAttribute('role', 'img')
    element.setAttribute(
      'aria-label',
      `${node.callsign}, ${node.role}, ${node.status}, ${node.latency_ms} milliseconds latency. Fictional exercise node.`,
    )
    element.innerHTML = `<strong>${node.callsign}</strong><span>${
      node.status === 'offline' ? 'OFFLINE' : handoff ? 'HANDOFF' : `${node.latency_ms} MS`
    }</span>`
    return new maplibregl.Marker({ element, anchor: 'bottom', offset: [0, -7] })
      .setLngLat([node.longitude, node.latitude])
      .addTo(map)
  })
}

export default function TacticalMap({ nodes, routes }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markersRef = useRef<Marker[]>([])
  const [mapReady, setMapReady] = useState(false)
  const [weather, setWeather] = useState<Weather | null>(null)
  const geoJson = useMemo(() => buildGeoJson(nodes, routes), [nodes, routes])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: MAP_CENTER,
      zoom: 5.5,
      minZoom: 4,
      maxZoom: 11,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm',
            paint: {
              'raster-saturation': -0.95,
              'raster-contrast': 0.3,
              'raster-brightness-min': 0.12,
              'raster-brightness-max': 0.5,
              'raster-opacity': 0.88,
            },
          },
        ],
      },
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')
    map.on('load', () => {
      markersRef.current = syncMarkers(map, nodes, markersRef.current)
      map.addSource('exercise-links', { type: 'geojson', data: geoJson.links })
      map.addSource('exercise-nodes', { type: 'geojson', data: geoJson.nodes })
      map.addLayer({
        id: 'exercise-links-active',
        type: 'line',
        source: 'exercise-links',
        filter: ['==', ['get', 'failed'], false],
        paint: {
          'line-color': '#85f0a8',
          'line-width': 1.4,
          'line-opacity': 0.65,
          'line-dasharray': [2, 2],
        },
      })
      map.addLayer({
        id: 'exercise-links-routed',
        type: 'line',
        source: 'exercise-links',
        filter: ['all', ['==', ['get', 'failed'], false], ['==', ['get', 'routed'], true]],
        paint: {
          'line-color': '#b8ffd0',
          'line-width': 2.6,
          'line-opacity': 0.85,
        },
      })
      map.addLayer({
        id: 'exercise-links-failed',
        type: 'line',
        source: 'exercise-links',
        filter: ['==', ['get', 'failed'], true],
        paint: {
          'line-color': '#f06e65',
          'line-width': 1,
          'line-opacity': 0.4,
          'line-dasharray': [1, 3],
        },
      })
      map.addLayer({
        id: 'exercise-nodes',
        type: 'circle',
        source: 'exercise-nodes',
        paint: {
          'circle-radius': ['case', ['get', 'coordinator'], 8, 5],
          'circle-color': [
            'match',
            ['get', 'status'],
            'offline', '#f06e65',
            'degraded', '#f4bd62',
            '#85f0a8',
          ],
          'circle-stroke-color': '#07100b',
          'circle-stroke-width': 2,
        },
      })
      setMapReady(true)
    })

    mapRef.current = map
    return () => {
      markersRef.current.forEach((marker) => marker.remove())
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    ;(map.getSource('exercise-links') as GeoJSONSource).setData(geoJson.links)
    ;(map.getSource('exercise-nodes') as GeoJSONSource).setData(geoJson.nodes)
    markersRef.current = syncMarkers(map, nodes, markersRef.current)
  }, [geoJson, mapReady, nodes])

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams({
      latitude: String(MAP_CENTER[1]),
      longitude: String(MAP_CENTER[0]),
      current: 'temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover',
      timezone: 'UTC',
    })
    fetch(`https://api.open-meteo.com/v1/forecast?${params}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Weather service unavailable')
        return response.json() as Promise<{
          current: {
            temperature_2m: number
            wind_speed_10m: number
            wind_direction_10m: number
            cloud_cover: number
            time: string
          }
        }>
      })
      .then(({ current }) => {
        setWeather({
          temperature: current.temperature_2m,
          windSpeed: current.wind_speed_10m,
          windDirection: current.wind_direction_10m,
          cloudCover: current.cloud_cover,
          observedAt: current.time,
        })
      })
      .catch(() => setWeather(null))
    return () => controller.abort()
  }, [])

  return (
    <div className="geo-map-shell">
      <div ref={containerRef} className="geo-map" aria-label="Real OpenStreetMap basemap with fictional exercise network overlay" />
      <div className="geo-map-vignette" aria-hidden="true" />
      <div className="map-readout map-readout-left">
        <span>PUBLIC BASEMAP</span>
        <strong>EASTERN EUROPE / OSM</strong>
      </div>
      <div className="map-readout map-readout-right">
        <span>OVERLAY</span>
        <strong>FICTIONAL EXERCISE</strong>
      </div>
      <div className="weather-readout" aria-live="polite">
        <span>OPEN-METEO / LIVE</span>
        {weather ? (
          <div>
            <strong>{weather.temperature.toFixed(1)}°C</strong>
            <small>WIND {weather.windSpeed.toFixed(0)} KM/H · {weather.windDirection.toFixed(0)}°</small>
            <small>CLOUD {weather.cloudCover}% · {weather.observedAt.slice(11)} UTC</small>
          </div>
        ) : (
          <strong>WEATHER UNAVAILABLE</strong>
        )}
      </div>
      <div className="map-legend">
        <span><i className="dot online" /> ONLINE</span>
        <span><i className="dot degraded" /> DEGRADED</span>
        <span><i className="dot offline" /> OFFLINE</span>
      </div>
    </div>
  )
}
