from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from extras.models import Graph, GRAPH_TYPE_PROVIDER
from utilities.forms import ConfirmationForm
from utilities.views import (
    BulkDeleteView, BulkEditView, BulkImportView, ObjectDeleteView, ObjectEditView, ObjectListView,
)

from . import filters, forms, tables
from .models import Circuit, CircuitTermination, CircuitType, Provider, TERM_SIDE_A, TERM_SIDE_Z


#
# Providers
#

class ProviderListView(ObjectListView):
    queryset = Provider.objects.annotate(count_circuits=Count('circuits'))
    filter = filters.ProviderFilter
    filter_form = forms.ProviderFilterForm
    table = tables.ProviderTable
    edit_permissions = ['circuits.change_provider', 'circuits.delete_provider']
    template_name = 'circuits/provider_list.html'


def provider(request, slug):

    provider = get_object_or_404(Provider, slug=slug)
    circuits = Circuit.objects.filter(provider=provider)
    show_graphs = Graph.objects.filter(type=GRAPH_TYPE_PROVIDER).exists()

    return render(request, 'circuits/provider.html', {
        'provider': provider,
        'circuits': circuits,
        'show_graphs': show_graphs,
    })


class ProviderEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'circuits.change_provider'
    model = Provider
    form_class = forms.ProviderForm
    template_name = 'circuits/provider_edit.html'
    obj_list_url = 'circuits:provider_list'


class ProviderDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'circuits.delete_provider'
    model = Provider
    default_return_url = 'circuits:provider_list'


class ProviderBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'circuits.add_provider'
    form = forms.ProviderImportForm
    table = tables.ProviderTable
    template_name = 'circuits/provider_import.html'
    obj_list_url = 'circuits:provider_list'


class ProviderBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'circuits.change_provider'
    cls = Provider
    form = forms.ProviderBulkEditForm
    template_name = 'circuits/provider_bulk_edit.html'
    default_redirect_url = 'circuits:provider_list'


class ProviderBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'circuits.delete_provider'
    cls = Provider
    default_redirect_url = 'circuits:provider_list'


#
# Circuit Types
#

class CircuitTypeListView(ObjectListView):
    queryset = CircuitType.objects.annotate(circuit_count=Count('circuits'))
    table = tables.CircuitTypeTable
    edit_permissions = ['circuits.change_circuittype', 'circuits.delete_circuittype']
    template_name = 'circuits/circuittype_list.html'


class CircuitTypeEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'circuits.change_circuittype'
    model = CircuitType
    form_class = forms.CircuitTypeForm

    def get_return_url(self, obj):
        return reverse('circuits:circuittype_list')


class CircuitTypeBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'circuits.delete_circuittype'
    cls = CircuitType
    default_redirect_url = 'circuits:circuittype_list'


#
# Circuits
#

class CircuitListView(ObjectListView):
    queryset = Circuit.objects.select_related('provider', 'type', 'tenant').prefetch_related('terminations__site')
    filter = filters.CircuitFilter
    filter_form = forms.CircuitFilterForm
    table = tables.CircuitTable
    edit_permissions = ['circuits.change_circuit', 'circuits.delete_circuit']
    template_name = 'circuits/circuit_list.html'


def circuit(request, pk):

    circuit = get_object_or_404(Circuit, pk=pk)
    termination_a = CircuitTermination.objects.filter(circuit=circuit, term_side=TERM_SIDE_A).first()
    termination_z = CircuitTermination.objects.filter(circuit=circuit, term_side=TERM_SIDE_Z).first()

    return render(request, 'circuits/circuit.html', {
        'circuit': circuit,
        'termination_a': termination_a,
        'termination_z': termination_z,
    })


class CircuitEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'circuits.change_circuit'
    model = Circuit
    form_class = forms.CircuitForm
    fields_initial = ['provider']
    template_name = 'circuits/circuit_edit.html'
    obj_list_url = 'circuits:circuit_list'


class CircuitDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'circuits.delete_circuit'
    model = Circuit
    default_return_url = 'circuits:circuit_list'


class CircuitBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'circuits.add_circuit'
    form = forms.CircuitImportForm
    table = tables.CircuitTable
    template_name = 'circuits/circuit_import.html'
    obj_list_url = 'circuits:circuit_list'


class CircuitBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'circuits.change_circuit'
    cls = Circuit
    form = forms.CircuitBulkEditForm
    template_name = 'circuits/circuit_bulk_edit.html'
    default_redirect_url = 'circuits:circuit_list'


class CircuitBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'circuits.delete_circuit'
    cls = Circuit
    default_redirect_url = 'circuits:circuit_list'


@permission_required('circuits.change_circuittermination')
def circuit_terminations_swap(request, pk):

    circuit = get_object_or_404(Circuit, pk=pk)
    termination_a = CircuitTermination.objects.filter(circuit=circuit, term_side=TERM_SIDE_A).first()
    termination_z = CircuitTermination.objects.filter(circuit=circuit, term_side=TERM_SIDE_Z).first()
    if not termination_a and not termination_z:
        messages.error(request, "No terminations have been defined for circuit {}.".format(circuit))
        return redirect('circuits:circuit', pk=circuit.pk)

    if request.method == 'POST':
        form = ConfirmationForm(request.POST)
        if form.is_valid():
            if termination_a and termination_z:
                # Use a placeholder to avoid an IntegrityError on the (circuit, term_side) unique constraint
                with transaction.atomic():
                    termination_a.term_side = '_'
                    termination_a.save()
                    termination_z.term_side = 'A'
                    termination_z.save()
                    termination_a.term_side = 'Z'
                    termination_a.save()
            elif termination_a:
                termination_a.term_side = 'Z'
                termination_a.save()
            else:
                termination_z.term_side = 'A'
                termination_z.save()
            messages.success(request, "Swapped terminations for circuit {}.".format(circuit))
            return redirect('circuits:circuit', pk=circuit.pk)

    else:
        form = ConfirmationForm()

    return render(request, 'circuits/circuit_terminations_swap.html', {
        'circuit': circuit,
        'termination_a': termination_a,
        'termination_z': termination_z,
        'form': form,
        'panel_class': 'default',
        'button_class': 'primary',
        'cancel_url': circuit.get_absolute_url(),
    })


#
# Circuit terminations
#

class CircuitTerminationEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'circuits.change_circuittermination'
    model = CircuitTermination
    form_class = forms.CircuitTerminationForm
    fields_initial = ['term_side']
    template_name = 'circuits/circuittermination_edit.html'

    def alter_obj(self, obj, args, kwargs):
        if 'circuit' in kwargs:
            obj.circuit = get_object_or_404(Circuit, pk=kwargs['circuit'])
        return obj

    def get_return_url(self, obj):
        return obj.circuit.get_absolute_url()


class CircuitTerminationDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'circuits.delete_circuittermination'
    model = CircuitTermination
