import h5py
import time

import numpy as np
import matplotlib.pyplot as plt

from IPython import display

HPLANCK = 6.626e-34 # SI
SC_GAP = 170e-6 # eV
RFLUX_Q = 2.067833848e-15/(2*np.pi)

#returns resistance in ohms
def R(V, Rbias, Vdiv, Vshort):
    if Vshort == 0 :
        return Rbias*(Vdiv/V - 1.)**(-1.)
    else:
        return Rbias*(Vdiv/V - 1.)**(-1.) - Rbias*(Vdiv/Vshort - 1.)**(-1.)

def Ic(V, Rbias, Vdiv, Vshort):
    return 0.5*np.pi * SC_GAP / R(V, Rbias, Vdiv, Vshort)
    
def Lj(V, Rbias, Vdiv, Vshort):
    return RFLUX_Q/Ic(V,Rbias,Vdiv,Vshort)
    
def Ej(V, Rbias, Vdiv, Vshort):
    return RFLUX_Q*Ic(V,Rbias,Vdiv,Vshort)/HPLANCK

def f(V, Rbias, Vdiv, Vshort, Ec):
    return (np.sqrt(8*Ec*Ej(V, Rbias, Vdiv, Vshort)) - Ec)

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

    def get_overloads(self):
        return np.where(self._voltages < 0, True, False)

    def get_shorts(self, threshold=2.5, relative=True):
        vals = np.where(self.get_overloads(), np.nan, self._voltages)

        if relative:
            mu = np.nanmean(vals)
            sigma = np.std(vals)

            threshold = mu - threshold*sigma

        shorts = np.where(vals < threshold, True, False)

        return shorts

    def get_opens(self, threshold=2.5, relative=True):
        vals = np.where(self.get_overloads(), np.nan, self._voltages)

        if relative:
            mu = np.nanmean(vals)
            sigma = np.std(vals)

            threshold = mu + threshold*sigma

        opens = np.where((vals > threshold) | np.isnan(vals), True, False)

        return opens

    def get_voltages(self, threshold=2.5, relative=True):
        try:
            ll, ul = threshold
        except TypeError:
            ll, ul = [threshold]*2

        shorts = self.get_shorts(ll, relative)
        opens = self.get_opens(ul, relative)

        vals = np.where(shorts|opens, np.nan, self._voltages)

        return vals

    def watch(self, mode='V', reload_time=1, ckwargs={}, pkwargs={}, **kwargs):
        scaling = {
            'V': 1e3,
            'Ic': 1e9,
            'R': 1,
            'f': 1e-9, 
        }[mode]

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
                vals *= scaling

                fig, ax = plot_value(vals, **pkwargs)
                fig.suptitle(f'Die X{lx}Y{ly}, Site {li}: {last*scaling:.4f} {unit}')
                fig.tight_layout()
                plt.show()
                time.sleep(reload_time)
                display.clear_output(wait=True)
            except KeyboardInterrupt:
                break