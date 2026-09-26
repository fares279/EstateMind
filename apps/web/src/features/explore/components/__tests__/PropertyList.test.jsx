import { fireEvent, render, screen } from '@testing-library/react';
import PropertyList from '../PropertyList';

const baseFilters = {
  governorate: '',
  delegation: '',
  property_type: '',
  price_min: '',
  price_max: '',
};

const properties = [
  {
    id: 1,
    title: 'Apartment A',
    price: 250000,
    type: 'Apartment',
    area: 90,
    rooms: 3,
    bathrooms: 1,
    location: 'Tunis, La Soukra',
    image: '/images/property_listing_placeholder.png',
    deal: 'good',
    tags: ['apartment', 'Local Agency'],
  },
  {
    id: 2,
    title: 'House B',
    price: 450000,
    type: 'House',
    area: 180,
    rooms: 5,
    bathrooms: 2,
    location: 'Ariana, Raoued',
    image: '/images/property_listing_placeholder.png',
    deal: 'fair',
    tags: ['house', 'Tayara'],
  },
];

describe('PropertyList', () => {
  test('renders properties from API payload', () => {
    render(
      <PropertyList
        properties={properties}
        selectedProperty={null}
        onPropertySelect={() => {}}
        onViewDetails={() => {}}
        filters={baseFilters}
        onFilterChange={() => {}}
        loading={false}
        error=""
      />
    );

    expect(screen.getByText(/2 properties found/i)).toBeInTheDocument();
    expect(screen.getByText('Apartment A')).toBeInTheDocument();
    expect(screen.getByText('House B')).toBeInTheDocument();
  });

  test('calls filter callback when reset is clicked', () => {
    const onFilterChange = jest.fn();

    render(
      <PropertyList
        properties={properties}
        selectedProperty={null}
        onPropertySelect={() => {}}
        onViewDetails={() => {}}
        filters={baseFilters}
        onFilterChange={onFilterChange}
        loading={false}
        error=""
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /reset filters/i }));

    expect(onFilterChange).toHaveBeenCalledWith({
      property_type: '',
      price_min: '',
      price_max: '',
      governorate: '',
      delegation: '',
    });
  });
});
