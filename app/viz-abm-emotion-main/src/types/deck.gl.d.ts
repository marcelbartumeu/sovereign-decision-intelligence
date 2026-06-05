import type { Component } from 'react';
import type { ViewState, Layer } from '@deck.gl/core';

declare module '@deck.gl/react' {
  interface DeckGLProps {
    viewState: ViewState;
    onViewStateChange: (params: { viewState: ViewState }) => void;
    controller: boolean;
    layers: Layer[];
    children?: React.ReactNode;
  }

  export default class DeckGL extends Component<DeckGLProps> {}
}

declare module '@deck.gl/layers' {
  import type { Layer, LayerProps } from '@deck.gl/core';

  export interface ScatterplotLayerProps<DataT> extends LayerProps {
    data: DataT[];
    getPosition: (d: DataT) => [number, number];
    getRadius?: (d: DataT) => number;
    getFillColor?: (d: DataT) => [number, number, number];
    radiusScale?: number;
    radiusMinPixels?: number;
    radiusMaxPixels?: number;
    lineWidthMinPixels?: number;
  }

  export class ScatterplotLayer<DataT = unknown> extends Layer<ScatterplotLayerProps<DataT>> {
    constructor(props: ScatterplotLayerProps<DataT>);
  }
} 