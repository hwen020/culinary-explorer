import {expect, test} from 'vitest'
import {coordinates, priceLabel} from './api'

test('labels missing and free prices separately', () => {
  expect(priceLabel(null)).toBe('Price unknown')
  expect(priceLabel(0)).toBe('Free')
  expect(priceLabel(3)).toBe('$$$')
})

test('formats selected map coordinates', () => {
  expect(coordinates({lat: 34.14213, lng: -118.01234})).toBe('34.1421, -118.0123')
})
