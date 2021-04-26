import h5py
import time

import numpy as np
import matplotlib.pyplot as plt

from IPython import display

HPLANCK = 6.626e-34 # SI
SC_GAP = 170e-6 # eV
RFLUX_Q = 2.067833848e-15/(2*np.pi)


def R(V, Rbias, Vdiv, Vshort, scaling=1e3):
    R = Rbias*(Vdiv/V - 1.)**(-1.)

    Rshort = Rbias * (Vdiv/Vshort - 1)**(-1) if Vshort else 0

    return (R - Rshort)/scaling

def Ic(V, Rbias, Vdiv, Vshort, scaling=1e-9):
    return 0.5*np.pi * SC_GAP / R(V, Rbias, Vdiv, Vshort, scaling=1)/scaling
    
def Lj(V, Rbias, Vdiv, Vshort, scaling=1e-9):
    return RFLUX_Q/Ic(V,Rbias,Vdiv,Vshort,scaling=1)/scaling
    
def Ej(V, Rbias, Vdiv, Vshort, scaling=1e9):
    return RFLUX_Q*Ic(V,Rbias,Vdiv,Vshort,scaling=1)/HPLANCK/scaling

def f(V, Rbias, Vdiv, Vshort, Ec, scaling=1e9):
    return np.sqrt(8*Ec*Ej(V, Rbias, Vdiv, Vshort), scaling=1)/scaling - Ec

def V(V, scaling=1e-3, **kwargs):
    return V/scaling

convert_funcs = {
    'R': R,
    'Ic': Ic,
    'Lj': Lj,
    'f': f,
    'V': V
}

def plot_value(vals, num_patterns=1, threshold=2.5, scaling=1, **kwargs):
    if len(vals.shape) > 2:
        vals = np.hstack(vals)

    rows, cols = vals.shape

    fig, axes = plt.subplots(1, num_patterns, figsize=(3.5*num_patterns, 3))
    for i in range(num_patterns):
        ax = axes[i] if num_patterns > 1 else axes
        im = ax.imshow(
            vals[i::num_patterns,:],
            origin='lower',
            aspect='auto',
        )

        fig.colorbar(im, ax=ax)

    return fig, axes


class ProbeAnalysis():
    """Analysis class."""

    def __init__(self, data_file, mask=np.s_[...]):
        self.mask = mask
        self.open(data_file)


    def open(self, data_file):
        self.h5file = h5py.File(data_file, 'r', libver='latest', swmr=True)
        self.reload()

    def close(self):
        self.h5file.close()

    def reload(self):
        self.h5file['last_probe'].refresh()
        self.h5file['voltages'].refresh()
        self.h5file['times'].refresh()

        self.last = self.h5file['last_probe'][...]
        self._voltages = self.h5file['voltages'][self.mask]
        self._times = self.h5file['times'][self.mask]
        try:
            self.Rbias = self.h5file.attrs['Rbias']
        except KeyError:
            self.Rbias = None
        try:
            self.Vdiv = self.h5file.attrs['Vdiv']
        except KeyError:
            self.Vdiv = None

    def get_overloads(self):
        return np.where(self._voltages < 0, True, False)

    def get_shorts(self, threshold=None, relative=True):
        if threshold is None:
            return np.zeros_like(self._voltages).astype(bool)


        vals = np.where(self.get_overloads(), np.nan, self._voltages)

        if relative:
            mu = np.nanmean(vals)
            sigma = np.nanstd(vals)

            threshold = mu - threshold*sigma

        shorts = np.where(vals < threshold, True, False)

        return shorts

    def get_opens(self, threshold=None, relative=True):
        if threshold is None:
            return np.where(self.get_overloads(), True, False)

        vals = np.where(self.get_overloads(), np.nan, self._voltages)

        if relative:
            mu = np.nanmean(vals)
            sigma = np.nanstd(vals)

            threshold = mu + threshold*sigma

        opens = np.where((vals > threshold) | np.isnan(vals), True, False)

        return opens

    def get_voltages(self, threshold=None, relative=True, subsite_shape=None, serpentine=False):
        try:
            ll, ul = threshold
        except TypeError:
            ll, ul = [threshold]*2

        shorts = self.get_shorts(ll, relative)
        opens = self.get_opens(ul, relative)

        vals = np.where(shorts|opens, np.nan, self._voltages)

        if subsite_shape is not None:
            x, y, sub = vals.shape
            vals = vals.transpose(1, 0, 2)

            sub_x, sub_y = subsite_shape
            vals = vals.reshape(y, x, sub_y, sub_x)

            if serpentine:
                vals[:,:, 1::2, :] = vals[:, :, 1::2, ::-1]
            vals = vals.transpose(0, 2, 1, 3,).reshape(y*sub_y, -1)


        return vals

    def plot(self, threshold=None, relative=True, subsite_shape=None, serpentine=False, mode='V', ckwargs={}):
        if subsite_shape is None:
            subsite_shape = (self._voltages.shape[-1], 1)
        vals = self.get_voltages(threshold=threshold, relative=relative, subsite_shape=subsite_shape, serpentine=serpentine)

        try:
            convert_kwargs = dict(Rbias=self.Rbias, Vdiv=self.Vdiv, Vshort=0)
            convert_kwargs.update(ckwargs)
            vals = convert_funcs[mode](vals, **convert_kwargs)
        except KeyError as e:
            raise ValueError('mode must be one of \'V\', \'R\', \'Ic\'. \'Lj\', \'f\'.')

        fig, ax = plt.subplots()

        im = ax.imshow(
            vals,
            origin='lower',
            aspect='auto',
        )

        fig.colorbar(im, ax=ax)
        return fig


    def watch(self, mode='V', reload_time=1, ckwargs={}, pkwargs={}, **kwargs):
        unit = {
            'V': 'mV',
            'Ic': 'nA',
            'R': 'Ω',
            'f': 'GHz'
        }[mode]

        convert = {
            'V': None,
            'Ic': Ic,
            'R': R,
            'f': f
        }[mode]

        fig = None
        while True:
            try:
                if fig: plt.close(fig)
                self.reload()
                lx, ly, li = self.last.astype('int')

                vals = self.get_voltages(**kwargs)

                idx = tuple(s for i, s in enumerate([lx, ly, li - 1]) if not isinstance(self.mask[i], int))
                last = vals[idx]

                if convert:
                    vals = convert(vals, **ckwargs)
                    last = convert(last, **ckwargs)

                fig, ax = plot_value(vals, **pkwargs)
                fig.suptitle(f'Die X{lx}Y{ly}, Site {li}: {last:.4f} {unit}')
                fig.tight_layout()
                plt.show()
                time.sleep(reload_time)
                display.clear_output(wait=True)
            except KeyboardInterrupt:
                break