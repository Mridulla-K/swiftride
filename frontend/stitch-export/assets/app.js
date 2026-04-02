// SwiftRide Frontend Application Logic

const USER_SERVICE_URL = 'http://localhost:8001/api/v1/users';
const RIDE_SERVICE_URL = 'http://localhost:8004/api/v1/rides';
const RIDE_SERVICE_WS_URL = 'ws://localhost:8004/api/v1/rides/ws';
const DRIVER_SERVICE_WS_URL = 'ws://localhost:8002/api/v1/drivers/ws/track';
const DRIVER_SERVICE_URL = 'http://localhost:8002/api/v1/drivers';
const PRICING_SERVICE_URL = 'http://localhost:8005/api/v1/pricing';
const INDIA_CENTER = [20.5937, 78.9629];
const INDIA_BOUNDS = [[6.5, 68.0], [37.5, 97.5]];
const TARGET_NEARBY_DRIVERS = 100;
const MIN_DRIVER_RADIUS_KM = 0.1;
const MAX_DRIVER_RADIUS_KM = 10;

let map = null;
let driverMarker = null;
let pickupMarker = null;
let dropoffMarker = null;
let pickupCoords = null;
let dropoffCoords = null;
let pickupMeta = null;
let dropoffMeta = null;
let mapSelectionMode = 'pickup';
let selectedVehicle = 'car';
let activeRideId = null;
let activeRideSocket = null;
let searchStartedAt = null;
let searchTimerInterval = null;
let searchTimeoutHandle = null;
let tipAmountInr = 0;
let nearbyDriverMarkers = [];
let driverEtaSeconds = null;
let driverEtaInterval = null;
let matchedVehicleType = 'car';
let activeDriverSocket = null;
let bookingInteractionEnabled = true;
let latestEstimatedFareInr = null;
let bookedFareInr = null;
let driverDistanceKm = null;

document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    const currentPath = window.location.pathname.split('/').pop() || 'index.html';

    if (currentPath === 'login.html') {
        if (token) {
            window.location.href = 'swift-ride-home.html';
            return;
        }
        setupAuthPage();
        return;
    }

    if (currentPath === 'swift-ride-home.html') {
        if (!token) {
            window.location.href = 'login.html';
            return;
        }
        setupHomePage();
    }
});

function parseJwt(token) {
    try {
        return JSON.parse(atob(token.split('.')[1]));
    } catch (_error) {
        return null;
    }
}

function getUserIdFromToken() {
    const token = localStorage.getItem('token');
    if (!token) {
        return null;
    }
    const decoded = parseJwt(token);
    return decoded && decoded.sub ? decoded.sub : null;
}

function parseLatLngInput(value, fallbackLat, fallbackLng) {
    if (!value || !value.includes(',')) {
        return { lat: fallbackLat, lng: fallbackLng };
    }
    const [latRaw, lngRaw] = value.split(',').map((item) => item.trim());
    const lat = Number(latRaw);
    const lng = Number(lngRaw);
    if (Number.isNaN(lat) || Number.isNaN(lng)) {
        return { lat: fallbackLat, lng: fallbackLng };
    }
    return { lat, lng };
}

function toRadians(value) {
    return (value * Math.PI) / 180;
}

function haversineDistanceKm(lat1, lng1, lat2, lng2) {
    const earthRadiusKm = 6371;
    const dLat = toRadians(lat2 - lat1);
    const dLng = toRadians(lng2 - lng1);
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * earthRadiusKm * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function randomPointAround(lat, lng, minRadiusKm, maxRadiusKm) {
    const distanceKm = minRadiusKm + Math.random() * (maxRadiusKm - minRadiusKm);
    const bearing = Math.random() * 2 * Math.PI;
    const earthRadiusKm = 6371;

    const latRad = toRadians(lat);
    const lngRad = toRadians(lng);
    const angularDistance = distanceKm / earthRadiusKm;

    const newLatRad = Math.asin(
        Math.sin(latRad) * Math.cos(angularDistance) +
        Math.cos(latRad) * Math.sin(angularDistance) * Math.cos(bearing)
    );

    const newLngRad = lngRad + Math.atan2(
        Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latRad),
        Math.cos(angularDistance) - Math.sin(latRad) * Math.sin(newLatRad)
    );

    return {
        lat: (newLatRad * 180) / Math.PI,
        lng: (newLngRad * 180) / Math.PI,
    };
}

function formatFieldName(rawField) {
    if (!rawField) {
        return null;
    }
    return rawField
        .replace(/_/g, ' ')
        .split(' ')
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function formatErrorText(text) {
    if (!text || typeof text !== 'string') {
        return 'Invalid value';
    }
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function getErrorMessage(errorData, fallback) {
    if (!errorData) {
        return fallback;
    }
    if (Array.isArray(errorData.detail)) {
        return errorData.detail
            .map((item) => {
                const loc = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
                const field = typeof loc === 'string' ? formatFieldName(loc) : null;
                const message = formatErrorText(item.msg || JSON.stringify(item));
                return field ? `${field}: ${message}` : message;
            })
            .join('; ');
    }
    if (typeof errorData.detail === 'string') {
        return errorData.detail;
    }
    if (typeof errorData.error === 'string') {
        return errorData.error;
    }
    return fallback;
}

// --- AUTHENTICATION PAGES ---

function setupAuthPage() {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const registerView = document.getElementById('register-view') || document.getElementById('register-card');
    const loginView = document.getElementById('login-view') || document.getElementById('login-card');
    const registerError = document.getElementById('register-error');
    const loginError = document.getElementById('login-error');

    if (!loginForm || !registerForm) {
        return;
    }

    if (showRegisterLink && registerView && loginView) {
        showRegisterLink.addEventListener('click', (e) => {
            e.preventDefault();
            loginView.classList.remove('form-visible');
            loginView.classList.add('form-hidden');
            registerView.classList.remove('form-hidden');
            registerView.classList.add('form-visible');
        });
    }

    if (showLoginLink && registerView && loginView) {
        showLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            registerView.classList.remove('form-visible');
            registerView.classList.add('form-hidden');
            loginView.classList.remove('form-hidden');
            loginView.classList.add('form-visible');
        });
    }

    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (registerError) {
            registerError.textContent = '';
            registerError.classList.add('hidden');
        }

        const fullName = registerForm.querySelector('#register-fullname')?.value?.trim();
        const email = registerForm.querySelector('#register-email')?.value?.trim();
        const password = registerForm.querySelector('#register-password')?.value;
        const phone = registerForm.querySelector('#register-phone')?.value?.trim();

        try {
            const response = await fetch(`${USER_SERVICE_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name: fullName, email, password, phone }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(getErrorMessage(errorData, 'Registration failed'));
            }

            if (registerError) {
                registerError.textContent = 'Registration successful. Please sign in.';
                registerError.classList.remove('hidden');
            }

            if (registerView && loginView) {
                registerView.classList.remove('form-visible');
                registerView.classList.add('form-hidden');
                loginView.classList.remove('form-hidden');
                loginView.classList.add('form-visible');
            }

            registerForm.reset();
        } catch (error) {
            if (registerError) {
                registerError.textContent = error.message;
                registerError.classList.remove('hidden');
            }
        }
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (loginError) {
            loginError.textContent = '';
            loginError.classList.add('hidden');
        }

        const email = loginForm.querySelector('#login-email')?.value?.trim();
        const password = loginForm.querySelector('#login-password')?.value;

        try {
            const response = await fetch(`${USER_SERVICE_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ email: email || '', password: password || '' }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(getErrorMessage(errorData, 'Login failed'));
            }

            const data = await response.json();
            localStorage.setItem('token', data.access_token);
            window.location.href = 'swift-ride-home.html';
        } catch (error) {
            if (loginError) {
                loginError.textContent = error.message;
                loginError.classList.remove('hidden');
            }
        }
    });
}

// --- HOME PAGE ---

function setupHomePage() {
    securePage();
    displayUserInfo();
    initMap();

    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('token');
            window.location.href = 'login.html';
        });
    }

    const rideRequestForm = document.getElementById('ride-request-form');
    if (rideRequestForm) {
        rideRequestForm.addEventListener('submit', handleRideRequest);
    }

    const pickupInput = document.getElementById('pickup-location');
    const dropoffInput = document.getElementById('dropoff-location');
    if (pickupInput) {
        pickupInput.addEventListener('blur', () => resolveInputAddress('pickup'));
    }
    if (dropoffInput) {
        dropoffInput.addEventListener('blur', () => resolveInputAddress('dropoff'));
    }

    const pickupModeButton = document.getElementById('select-pickup-point');
    const dropoffModeButton = document.getElementById('select-dropoff-point');
    if (pickupModeButton) {
        pickupModeButton.addEventListener('click', () => setMapSelectionMode('pickup'));
    }
    if (dropoffModeButton) {
        dropoffModeButton.addEventListener('click', () => setMapSelectionMode('dropoff'));
    }

    setupVehicleSelector();
    setupNoDriverActions();
    setupCancelRideActions();
    setupEditRouteActions();
    setBookingInteractionEnabled(true);
    updateMapSelectionUi();
    clearNearbyDriverMarkers();
}

async function handleRideRequest(event) {
    event.preventDefault();
    const token = localStorage.getItem('token');
    const riderId = getUserIdFromToken();
    const pickupLocation = document.getElementById('pickup-location')?.value || '';
    const dropoffLocation = document.getElementById('dropoff-location')?.value || '';

    if (!token || !riderId) {
        alert('Session expired. Please sign in again.');
        window.location.href = 'login.html';
        return;
    }

    const pickup = await resolveLocationForRide('pickup', pickupLocation);
    const dropoff = await resolveLocationForRide('dropoff', dropoffLocation);

    if (!pickup || !dropoff) {
        alert('Please set valid pickup and dropoff locations by map click or address search.');
        return;
    }

    await seedDriversAroundPickup(pickup);

    const tripValidation = validateTripBoundary();
    if (!tripValidation.ok) {
        alert(tripValidation.message);
        return;
    }

    const payload = {
        rider_id: riderId,
        pickup_lat: pickup.lat,
        pickup_lng: pickup.lng,
        dropoff_lat: dropoff.lat,
        dropoff_lng: dropoff.lng,
        pickup_address: pickupLocation,
        dropoff_address: dropoffLocation,
        vehicle_type: selectedVehicle,
    };

    const quoteAtBooking = Number(latestEstimatedFareInr);
    bookedFareInr = Number.isFinite(quoteAtBooking) ? quoteAtBooking : null;

    try {
        const response = await fetch(RIDE_SERVICE_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => null);
            throw new Error(getErrorMessage(err, 'Failed to request ride'));
        }

        const ride = await response.json();
        activeRideId = ride.id;
        showFindingDriverCard();
        connectToRideSocket(ride.id);
    } catch (error) {
        alert(error.message);
    }
}

async function createMockDriver(index, pickup) {
    const runTag = Date.now();
    const unique = `${runTag}${index}${Math.floor(Math.random() * 1000)}`;
    const location = randomPointAround(pickup.lat, pickup.lng, MIN_DRIVER_RADIUS_KM, MAX_DRIVER_RADIUS_KM);
    const vehicleChoices = ['Honda Activa Scooter', 'Bajaj Auto Rickshaw', 'Maruti Suzuki Dzire', 'Hyundai i20', 'TVS Apache Bike'];
    const vehicleModel = vehicleChoices[index % vehicleChoices.length];

    const createResponse = await fetch(`${DRIVER_SERVICE_URL}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            full_name: `Pickup Driver ${index + 1}`,
            phone: `9${unique}`.slice(0, 10),
            email: `pickup_driver_${unique}@swiftride.dev`,
            license_number: `LIC-${unique}`,
            vehicle_model: vehicleModel,
            vehicle_plate: `KA01${String(index).padStart(4, '0')}`,
        }),
    });

    if (!createResponse.ok) {
        return null;
    }

    const driver = await createResponse.json();
    await fetch(`${DRIVER_SERVICE_URL}/${driver.id}/location`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: location.lat, lng: location.lng }),
    });
    await fetch(`${DRIVER_SERVICE_URL}/${driver.id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'available' }),
    });

    return driver;
}

async function seedDriversAroundPickup(pickup) {
    try {
        const response = await fetch(`${DRIVER_SERVICE_URL}?status_filter=available&limit=500`);
        if (!response.ok) {
            return;
        }

        let drivers = await response.json();
        const nearbyExisting = drivers.filter((driver) => {
            if (typeof driver.current_lat !== 'number' || typeof driver.current_lng !== 'number') {
                return false;
            }
            const distance = haversineDistanceKm(pickup.lat, pickup.lng, driver.current_lat, driver.current_lng);
            return distance >= MIN_DRIVER_RADIUS_KM && distance <= MAX_DRIVER_RADIUS_KM;
        });

        let selected = nearbyExisting.slice(0, TARGET_NEARBY_DRIVERS);
        if (selected.length < TARGET_NEARBY_DRIVERS) {
            const additionalNeeded = TARGET_NEARBY_DRIVERS - selected.length;
            const createTasks = [];
            for (let i = 0; i < additionalNeeded; i += 1) {
                createTasks.push(createMockDriver(i, pickup));
            }
            const created = (await Promise.all(createTasks)).filter(Boolean);
            drivers = drivers.concat(created);
        }

        selected = drivers.slice(0, TARGET_NEARBY_DRIVERS);
        const updates = selected.map(async (driver) => {
            const location = randomPointAround(pickup.lat, pickup.lng, MIN_DRIVER_RADIUS_KM, MAX_DRIVER_RADIUS_KM);
            await fetch(`${DRIVER_SERVICE_URL}/${driver.id}/location`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat: location.lat, lng: location.lng }),
            });
            await fetch(`${DRIVER_SERVICE_URL}/${driver.id}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'available' }),
            });
        });
        await Promise.all(updates);
        loadNearbyDrivers();
    } catch (_error) {
        // Non-critical helper step; ride request can still continue.
    }
}

function connectToRideSocket(rideId) {
    if (activeRideSocket) {
        activeRideSocket.close();
    }

    const socket = new WebSocket(`${RIDE_SERVICE_WS_URL}/${rideId}`);
    activeRideSocket = socket;
    startDriverSearchCountdown();

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'ride.matched') {
            stopDriverSearchCountdown();
            const driver = {
                id: data.driver_id,
                name: data.driver_name,
                vehicle: data.vehicle,
                rating: data.driver_rating,
                fareInr: data.estimated_fare_inr,
                initialDistanceKm: data.distance_km,
                initialEtaSeconds: data.estimated_pickup_seconds,
            };
            showDriverMatchedCard(driver);
            connectToDriverLocationSocket(rideId);
        }
    };
}

function connectToDriverLocationSocket(rideId) {
    if (activeDriverSocket) {
        activeDriverSocket.close();
    }

    const socket = new WebSocket(`${DRIVER_SERVICE_WS_URL}/${rideId}`);
    activeDriverSocket = socket;

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'driver.location.update') {
            const latLng = [data.lat, data.lng];
            if (driverMarker) {
                driverMarker.setLatLng(latLng);
            } else {
                driverMarker = L.marker(latLng).addTo(map);
            }

            if (pickupCoords) {
                const distanceKm = haversineDistanceKm(pickupCoords.lat, pickupCoords.lng, data.lat, data.lng);
                const etaSeconds = estimateEtaSeconds(distanceKm, matchedVehicleType);
                startDriverEtaCountdown(etaSeconds, true, distanceKm);
            }

            map.setView(latLng, 15);
        }
    };
}

function showFindingDriverCard() {
    setBookingInteractionEnabled(true);
    document.getElementById('ride-request-card')?.classList.add('hidden');
    document.getElementById('no-driver-card')?.classList.add('hidden');
    document.getElementById('driver-matched-card')?.classList.add('hidden');
    stopDriverEtaCountdown();
    document.getElementById('finding-driver-card')?.classList.remove('hidden');
}

function showDriverMatchedCard(driver) {
    setBookingInteractionEnabled(false);
    document.getElementById('ride-request-card')?.classList.add('hidden');
    document.getElementById('finding-driver-card')?.classList.add('hidden');
    document.getElementById('no-driver-card')?.classList.add('hidden');

    const driverName = document.getElementById('driver-name');
    const driverVehicle = document.getElementById('driver-vehicle');
    const driverRating = document.getElementById('driver-rating');
    const driverFare = document.getElementById('driver-fare');
    const driverDistance = document.getElementById('driver-distance');
    const driverEta = document.getElementById('driver-eta');
    if (driverName) {
        driverName.textContent = driver.name || 'Assigned Driver';
    }
    if (driverVehicle && driver.vehicle) {
        const model = driver.vehicle.model || 'Vehicle';
        const plate = driver.vehicle.license_plate || 'N/A';
        driverVehicle.textContent = `${model} (${plate})`;
    }

    const normalizedRating = Number(driver.rating);
    const normalizedFare = Number(driver.fareInr);
    const lockedBookedFare = Number(bookedFareInr);
    const fallbackFare = Number(latestEstimatedFareInr);
    const fareToShow = Number.isFinite(lockedBookedFare)
        ? lockedBookedFare
        : (Number.isFinite(fallbackFare) ? fallbackFare : normalizedFare);

    if (driverRating) {
        driverRating.textContent = Number.isFinite(normalizedRating)
            ? `Rating: ${normalizedRating.toFixed(1)} ★`
            : 'Rating: N/A';
    }
    if (driverFare) {
        driverFare.textContent = Number.isFinite(fareToShow)
            ? `Estimated Fare: ${formatInr(fareToShow)}`
            : 'Estimated Fare: N/A';
    }

    matchedVehicleType = driver?.vehicle?.type || getVehicleTypeFromModel(driver?.vehicle?.model || '');
    const initialDistanceFromEvent = Number(driver.initialDistanceKm);
    const initialDistanceKm = Number.isFinite(initialDistanceFromEvent)
        ? initialDistanceFromEvent
        : estimateInitialDriverDistanceKm();
    const initialEtaFromEvent = Number(driver.initialEtaSeconds);
    const initialEtaSeconds = Number.isFinite(initialEtaFromEvent) ? initialEtaFromEvent : 10;
    if (driverDistance) {
        driverDistance.textContent = Number.isFinite(initialDistanceKm)
            ? `Distance to pickup: ${initialDistanceKm.toFixed(2)} km`
            : 'Distance to pickup: syncing live...';
    }
    if (driverEta) {
        driverEta.textContent = `ETA (traffic adjusted): ${formatEta(initialEtaSeconds)}`;
    }
    startDriverEtaCountdown(initialEtaSeconds, true, initialDistanceKm);

    document.getElementById('driver-matched-card')?.classList.remove('hidden');
}

function showNoDriverCard() {
    setBookingInteractionEnabled(true);
    document.getElementById('ride-request-card')?.classList.add('hidden');
    document.getElementById('finding-driver-card')?.classList.add('hidden');
    document.getElementById('no-driver-card')?.classList.remove('hidden');
}

function setupNoDriverActions() {
    const retryButton = document.getElementById('retry-find-driver');
    if (retryButton) {
        retryButton.addEventListener('click', () => {
            if (activeRideId) {
                showFindingDriverCard();
                connectToRideSocket(activeRideId);
            }
        });
    }

    const noTipButton = document.getElementById('no-tip-option');
    if (noTipButton) {
        noTipButton.addEventListener('click', () => {
            tipAmountInr = 0;
            const tipButtons = document.querySelectorAll('.tip-option');
            tipButtons.forEach((item) => {
                item.classList.remove('bg-primary-container', 'text-on-primary-container');
                item.classList.add('bg-outline-variant');
            });
            updateFareEstimate();

            if (activeRideId) {
                showFindingDriverCard();
                connectToRideSocket(activeRideId);
            }
        });
    }

    const tipButtons = document.querySelectorAll('.tip-option');
    tipButtons.forEach((button) => {
        button.addEventListener('click', () => {
            tipAmountInr = Number(button.dataset.tip || '0');
            tipButtons.forEach((item) => {
                item.classList.remove('bg-primary-container', 'text-on-primary-container');
                item.classList.add('bg-outline-variant');
            });
            button.classList.remove('bg-outline-variant');
            button.classList.add('bg-primary-container', 'text-on-primary-container');
            updateFareEstimate();
        });
    });
}

function setupCancelRideActions() {
    const buttons = document.querySelectorAll('.cancel-ride-button');
    buttons.forEach((button) => {
        button.addEventListener('click', async () => {
            await cancelActiveRide();
        });
    });
}

function setupEditRouteActions() {
    const buttons = document.querySelectorAll('.edit-route-button');
    buttons.forEach((button) => {
        button.addEventListener('click', async () => {
            await cancelActiveRide({ silent: true, suppressAlert: true });
        });
    });
}

async function cancelActiveRide(options = {}) {
    const { silent = false, suppressAlert = false } = options;

    if (!activeRideId) {
        if (!silent) {
            alert('No active ride to cancel.');
        }
        return;
    }

    try {
        const response = await fetch(`${RIDE_SERVICE_URL}/${activeRideId}/cancel`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            const err = await response.json().catch(() => null);
            throw new Error(getErrorMessage(err, 'Failed to cancel ride'));
        }

        stopDriverSearchCountdown();
        stopDriverEtaCountdown();
        if (activeRideSocket) {
            activeRideSocket.close();
            activeRideSocket = null;
        }
        if (activeDriverSocket) {
            activeDriverSocket.close();
            activeDriverSocket = null;
        }

        activeRideId = null;
        tipAmountInr = 0;
        bookedFareInr = null;
        setBookingInteractionEnabled(true);

        document.getElementById('finding-driver-card')?.classList.add('hidden');
        document.getElementById('no-driver-card')?.classList.add('hidden');
        document.getElementById('driver-matched-card')?.classList.add('hidden');
        document.getElementById('ride-request-card')?.classList.remove('hidden');

        if (!suppressAlert) {
            alert('Ride cancelled successfully.');
        }
        updateFareEstimate();
    } catch (error) {
        alert(error.message);
    }
}

function startDriverSearchCountdown() {
    stopDriverSearchCountdown();
    searchStartedAt = Date.now();
    const timerEl = document.getElementById('search-timer');
    if (timerEl) {
        timerEl.textContent = 'Time elapsed: 0s';
    }

    searchTimerInterval = setInterval(() => {
        if (!searchStartedAt || !timerEl) {
            return;
        }
        const elapsedSeconds = Math.floor((Date.now() - searchStartedAt) / 1000);
        timerEl.textContent = `Time elapsed: ${elapsedSeconds}s`;
    }, 1000);

    searchTimeoutHandle = setTimeout(() => {
        showNoDriverCard();
    }, 120000);
}

function stopDriverSearchCountdown() {
    if (searchTimerInterval) {
        clearInterval(searchTimerInterval);
        searchTimerInterval = null;
    }
    if (searchTimeoutHandle) {
        clearTimeout(searchTimeoutHandle);
        searchTimeoutHandle = null;
    }
    searchStartedAt = null;
}

function getTrafficMultiplier() {
    const hour = new Date().getHours();
    let multiplier = 1.0;
    if ((hour >= 8 && hour <= 11) || (hour >= 17 && hour <= 21)) {
        multiplier = 1.18;
    } else if ((hour >= 12 && hour <= 16) || (hour >= 22 && hour <= 23)) {
        multiplier = 1.08;
    }
    const randomSwing = 0.97 + Math.random() * 0.1;
    return multiplier * randomSwing;
}

function estimateInitialDriverDistanceKm() {
    if (!pickupCoords || nearbyDriverMarkers.length === 0) {
        return null;
    }

    let closestDistance = null;
    nearbyDriverMarkers.forEach((marker) => {
        const point = marker.getLatLng();
        const distance = haversineDistanceKm(pickupCoords.lat, pickupCoords.lng, point.lat, point.lng);
        if (closestDistance === null || distance < closestDistance) {
            closestDistance = distance;
        }
    });

    return closestDistance;
}

function estimateEtaSeconds(distanceKm, vehicleType) {
    const speedsKmPerMin = {
        bike: 0.62,
        auto: 0.5,
        car: 0.58,
    };
    const speed = speedsKmPerMin[vehicleType] || speedsKmPerMin.car;
    const traffic = getTrafficMultiplier();
    const minutes = (distanceKm / speed) * traffic;
    return Math.min(18 * 60, Math.max(30, Math.round(minutes * 60)));
}

function formatEta(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
}

function updateDriverApproachInfo(distanceKm, etaSeconds) {
    const driverDistance = document.getElementById('driver-distance');
    const driverEta = document.getElementById('driver-eta');
    const driverStatusMessage = document.getElementById('driver-status-message');
    if (driverDistance && Number.isFinite(distanceKm)) {
        driverDistance.textContent = `Distance to pickup: ${distanceKm.toFixed(2)} km`;
    }
    if (driverEta && Number.isFinite(etaSeconds)) {
        driverEta.textContent = `ETA (traffic adjusted): ${formatEta(Math.max(0, etaSeconds))}`;
    }
    if (driverStatusMessage && Number.isFinite(etaSeconds)) {
        driverStatusMessage.textContent = etaSeconds <= 0
            ? 'Your driver has arrived.'
            : 'Your driver is on the way.';
    }
}

function stopDriverEtaCountdown() {
    if (driverEtaInterval) {
        clearInterval(driverEtaInterval);
        driverEtaInterval = null;
    }
    driverEtaSeconds = null;
    driverDistanceKm = null;
}

function startDriverEtaCountdown(initialSeconds, forceReset = false, initialDistanceKm = undefined) {
    const normalized = Math.max(0, Math.round(initialSeconds));
    if (forceReset || driverEtaSeconds === null) {
        driverEtaSeconds = normalized;
    } else {
        // Keep ETA moving down instead of jumping up on noisy GPS refreshes.
        driverEtaSeconds = Math.min(driverEtaSeconds, normalized);
    }

    if (Number.isFinite(initialDistanceKm)) {
        if (forceReset || driverDistanceKm === null) {
            driverDistanceKm = initialDistanceKm;
        } else {
            driverDistanceKm = Math.min(driverDistanceKm, initialDistanceKm);
        }
    }

    updateDriverApproachInfo(driverDistanceKm, driverEtaSeconds);

    if (!driverEtaInterval) {
        driverEtaInterval = setInterval(() => {
            if (driverEtaSeconds === null) {
                return;
            }

            if (Number.isFinite(driverDistanceKm)) {
                const remainingBeforeTick = Math.max(1, driverEtaSeconds);
                const step = driverDistanceKm / remainingBeforeTick;
                driverDistanceKm = Math.max(0, driverDistanceKm - step);
            }

            driverEtaSeconds = Math.max(0, driverEtaSeconds - 1);
            updateDriverApproachInfo(driverDistanceKm, driverEtaSeconds);
            if (driverEtaSeconds <= 0) {
                stopDriverEtaCountdown();
            }
        }, 1000);
    }
}

function initMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl || typeof L === 'undefined') {
        return;
    }

    map = L.map('map', { minZoom: 4, maxZoom: 19 });
    map.fitBounds(INDIA_BOUNDS);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
    }).addTo(map);

    map.on('click', async (event) => {
        if (!bookingInteractionEnabled) {
            return;
        }
        if (mapSelectionMode === 'pickup') {
            await setPointFromMapClick('pickup', event.latlng.lat, event.latlng.lng);
            setMapSelectionMode('dropoff');
            return;
        }
        await setPointFromMapClick('dropoff', event.latlng.lat, event.latlng.lng);
    });

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((position) => {
            const userLatLng = [position.coords.latitude, position.coords.longitude];
            map.setView(userLatLng, 13);
            L.marker(userLatLng).addTo(map).bindPopup('You are here.').openPopup();

            if (isInsideIndia(userLatLng[0], userLatLng[1])) {
                // Do not auto-pick pickup point on login; user explicitly chooses pickup.
            } else {
                map.setView(INDIA_CENTER, 5);
            }
        });
    }
}

function isInsideIndia(lat, lng) {
    return lat >= INDIA_BOUNDS[0][0] && lat <= INDIA_BOUNDS[1][0] && lng >= INDIA_BOUNDS[0][1] && lng <= INDIA_BOUNDS[1][1];
}

function setupVehicleSelector() {
    const options = document.querySelectorAll('.vehicle-option');
    options.forEach((button) => {
        button.addEventListener('click', () => {
            selectedVehicle = button.dataset.vehicle || 'car';
            options.forEach((item) => {
                item.classList.remove('bg-primary-container', 'text-on-primary-container');
                item.classList.add('bg-outline-variant');
            });
            button.classList.remove('bg-outline-variant');
            button.classList.add('bg-primary-container', 'text-on-primary-container');
            updateFareEstimate();
        });
    });
}

function updateMapSelectionUi() {
    const pickupModeButton = document.getElementById('select-pickup-point');
    const dropoffModeButton = document.getElementById('select-dropoff-point');
    const hint = document.getElementById('map-selection-hint');

    if (pickupModeButton && dropoffModeButton) {
        if (mapSelectionMode === 'pickup') {
            pickupModeButton.classList.add('bg-primary-container', 'text-on-primary-container');
            pickupModeButton.classList.remove('bg-outline-variant');
            dropoffModeButton.classList.remove('bg-primary-container', 'text-on-primary-container');
            dropoffModeButton.classList.add('bg-outline-variant');
        } else {
            dropoffModeButton.classList.add('bg-primary-container', 'text-on-primary-container');
            dropoffModeButton.classList.remove('bg-outline-variant');
            pickupModeButton.classList.remove('bg-primary-container', 'text-on-primary-container');
            pickupModeButton.classList.add('bg-outline-variant');
        }
    }

    if (hint) {
        hint.textContent = `Map click mode: ${formatFieldName(mapSelectionMode)}`;
    }
}

function setMapSelectionMode(mode) {
    if (!bookingInteractionEnabled) {
        return;
    }
    mapSelectionMode = mode;
    updateMapSelectionUi();
}

function setBookingInteractionEnabled(enabled) {
    bookingInteractionEnabled = enabled;

    const pickupModeButton = document.getElementById('select-pickup-point');
    const dropoffModeButton = document.getElementById('select-dropoff-point');
    const pickupInput = document.getElementById('pickup-location');
    const dropoffInput = document.getElementById('dropoff-location');

    [pickupModeButton, dropoffModeButton].forEach((button) => {
        if (!button) {
            return;
        }
        button.disabled = !enabled;
        button.classList.toggle('opacity-60', !enabled);
        button.classList.toggle('cursor-not-allowed', !enabled);
    });

    [pickupInput, dropoffInput].forEach((input) => {
        if (!input) {
            return;
        }
        input.readOnly = !enabled;
    });
}

function setPointMarker(kind, lat, lng) {
    if (!map) {
        return;
    }

    const marker = kind === 'pickup' ? pickupMarker : dropoffMarker;
    if (marker) {
        marker.setLatLng([lat, lng]);
    } else {
        const newMarker = L.marker([lat, lng]).addTo(map);
        if (kind === 'pickup') {
            pickupMarker = newMarker;
        } else {
            dropoffMarker = newMarker;
        }
    }

    if (kind === 'pickup') {
        pickupCoords = { lat, lng };
        loadNearbyDrivers();
    } else {
        dropoffCoords = { lat, lng };
    }
}

function setPointMeta(kind, meta) {
    if (kind === 'pickup') {
        pickupMeta = meta;
    } else {
        dropoffMeta = meta;
    }
}

function extractAddressMeta(nominatimData) {
    if (!nominatimData || !nominatimData.address) {
        return null;
    }

    const address = nominatimData.address;
    const state = address.state || address.state_district || null;
    const country = address.country || null;
    const countryCode = address.country_code ? String(address.country_code).toUpperCase() : null;

    return {
        state,
        country,
        countryCode,
    };
}

function validateTripBoundary() {
    if (!pickupMeta || !dropoffMeta) {
        return {
            ok: false,
            message: 'Please select valid pickup and dropoff addresses so we can validate trip boundaries.',
        };
    }

    if (pickupMeta.countryCode !== 'IN' || dropoffMeta.countryCode !== 'IN') {
        return {
            ok: false,
            message: 'Cross-country rides are not allowed. Pickup and dropoff must both be in India.',
        };
    }

    if (!pickupMeta.state || !dropoffMeta.state) {
        return {
            ok: false,
            message: 'Could not determine state for one of the locations. Please choose a more specific address.',
        };
    }

    if (pickupMeta.state.trim().toLowerCase() !== dropoffMeta.state.trim().toLowerCase()) {
        return {
            ok: false,
            message: 'Inter-state rides are not allowed. Pickup and dropoff must be within the same state.',
        };
    }

    return { ok: true, message: '' };
}

async function setPointFromMapClick(kind, lat, lng) {
    if (!bookingInteractionEnabled) {
        return;
    }

    if (!isInsideIndia(lat, lng)) {
        alert('Please choose a point within India.');
        return;
    }

    setPointMarker(kind, lat, lng);
    const input = document.getElementById(kind === 'pickup' ? 'pickup-location' : 'dropoff-location');
    const location = await reverseGeocode(lat, lng);
    setPointMeta(kind, location ? location.meta : null);
    if (input) {
        input.value = (location && location.address) || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }
    updateFareEstimate();
}

function tryParseLatLng(value) {
    if (!value || !value.includes(',')) {
        return null;
    }
    const [latRaw, lngRaw] = value.split(',').map((item) => item.trim());
    const lat = Number(latRaw);
    const lng = Number(lngRaw);
    if (Number.isNaN(lat) || Number.isNaN(lng)) {
        return null;
    }
    return { lat, lng };
}

async function geocodeAddress(query) {
    if (!query) {
        return null;
    }
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=1&countrycodes=in&q=${encodeURIComponent(query)}`);
    if (!response.ok) {
        return null;
    }
    const data = await response.json();
    if (!Array.isArray(data) || data.length === 0) {
        return null;
    }
    const first = data[0];
    return {
        lat: Number(first.lat),
        lng: Number(first.lon),
        address: first.display_name,
        meta: extractAddressMeta(first),
    };
}

async function reverseGeocode(lat, lng) {
    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&lat=${lat}&lon=${lng}`);
    if (!response.ok) {
        return null;
    }
    const data = await response.json();
    return {
        address: data.display_name || null,
        meta: extractAddressMeta(data),
    };
}

async function resolveInputAddress(kind) {
    if (!bookingInteractionEnabled) {
        return;
    }

    const input = document.getElementById(kind === 'pickup' ? 'pickup-location' : 'dropoff-location');
    if (!input || !input.value.trim()) {
        return;
    }

    const parsed = tryParseLatLng(input.value.trim());
    if (parsed && isInsideIndia(parsed.lat, parsed.lng)) {
        setPointMarker(kind, parsed.lat, parsed.lng);
        const location = await reverseGeocode(parsed.lat, parsed.lng);
        setPointMeta(kind, location ? location.meta : null);
        if (location && location.address) {
            input.value = location.address;
        }
        updateFareEstimate();
        return;
    }

    const geocoded = await geocodeAddress(input.value.trim());
    if (!geocoded || !isInsideIndia(geocoded.lat, geocoded.lng)) {
        return;
    }

    setPointMarker(kind, geocoded.lat, geocoded.lng);
    setPointMeta(kind, geocoded.meta || null);
    input.value = geocoded.address;
    if (map) {
        map.setView([geocoded.lat, geocoded.lng], 14);
    }
    updateFareEstimate();
}

async function resolveLocationForRide(kind, rawValue) {
    const currentCoords = kind === 'pickup' ? pickupCoords : dropoffCoords;
    if (currentCoords) {
        return currentCoords;
    }

    const parsed = tryParseLatLng(rawValue);
    if (parsed && isInsideIndia(parsed.lat, parsed.lng)) {
        if ((kind === 'pickup' && !pickupMeta) || (kind === 'dropoff' && !dropoffMeta)) {
            const location = await reverseGeocode(parsed.lat, parsed.lng);
            setPointMeta(kind, location ? location.meta : null);
        }
        return parsed;
    }

    const geocoded = await geocodeAddress(rawValue);
    if (geocoded && isInsideIndia(geocoded.lat, geocoded.lng)) {
        setPointMeta(kind, geocoded.meta || null);
        return { lat: geocoded.lat, lng: geocoded.lng };
    }

    return null;
}

async function updateFareEstimate() {
    const fareEstimate = document.getElementById('fare-estimate');
    if (!fareEstimate) {
        return;
    }

    if (!pickupCoords || !dropoffCoords) {
        fareEstimate.textContent = 'Choose pickup and dropoff to get fare estimate.';
        return;
    }

    const tripValidation = validateTripBoundary();
    if (!tripValidation.ok) {
        fareEstimate.textContent = tripValidation.message;
        return;
    }

    try {
        const response = await fetch(`${PRICING_SERVICE_URL}/estimate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pickup_lat: pickupCoords.lat,
                pickup_lng: pickupCoords.lng,
                dropoff_lat: dropoffCoords.lat,
                dropoff_lng: dropoffCoords.lng,
                vehicle_type: selectedVehicle,
            }),
        });

        if (!response.ok) {
            fareEstimate.textContent = 'Could not estimate fare right now.';
            return;
        }

        const estimate = await response.json();
        const adjustedFare = estimate.final_fare + tipAmountInr;
        latestEstimatedFareInr = adjustedFare;
        fareEstimate.textContent = `Est. ${formatFieldName(selectedVehicle)} fare (${estimate.distance_km} km): ${formatInr(adjustedFare)}${tipAmountInr > 0 ? ` (incl. ${formatInr(tipAmountInr)} tip)` : ''}`;
    } catch (_error) {
        fareEstimate.textContent = 'Could not estimate fare right now.';
    }
}

function formatInr(amount) {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
}

function getVehicleTypeFromModel(model) {
    const value = String(model || '').toLowerCase();
    if (value.includes('bike') || value.includes('moto') || value.includes('scooter')) {
        return 'bike';
    }
    if (value.includes('auto') || value.includes('rickshaw')) {
        return 'auto';
    }
    return 'car';
}

function getVehicleIconGlyph(vehicleType) {
    if (vehicleType === 'bike') {
        return '🏍️';
    }
    if (vehicleType === 'auto') {
        return '🛺';
    }
    return '🚗';
}

function clearNearbyDriverMarkers() {
    nearbyDriverMarkers.forEach((marker) => marker.remove());
    nearbyDriverMarkers = [];
}

function makeVehicleMarkerIcon(vehicleType) {
    const glyph = getVehicleIconGlyph(vehicleType);
    return L.divIcon({
        className: 'vehicle-marker',
        html: `<div style="background:rgba(0,0,0,0.65);color:#fff;border:1px solid #b3c5ff;border-radius:999px;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:16px;">${glyph}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
    });
}

async function loadNearbyDrivers() {
    if (!map) {
        return;
    }

    if (!pickupCoords) {
        clearNearbyDriverMarkers();
        return;
    }

    try {
        const response = await fetch(`${DRIVER_SERVICE_URL}?status_filter=available&limit=500`);
        if (!response.ok) {
            return;
        }

        const drivers = await response.json();
        clearNearbyDriverMarkers();

        drivers.forEach((driver) => {
            if (typeof driver.current_lat !== 'number' || typeof driver.current_lng !== 'number') {
                return;
            }
            const distanceKm = haversineDistanceKm(pickupCoords.lat, pickupCoords.lng, driver.current_lat, driver.current_lng);
            if (distanceKm < MIN_DRIVER_RADIUS_KM || distanceKm > MAX_DRIVER_RADIUS_KM) {
                return;
            }
            const type = getVehicleTypeFromModel(driver.vehicle_model);
            const marker = L.marker([driver.current_lat, driver.current_lng], { icon: makeVehicleMarkerIcon(type) }).addTo(map);
            marker.bindPopup(`${formatFieldName(type)} nearby`);
            nearbyDriverMarkers.push(marker);
        });
    } catch (_error) {
        // Non-critical UI enhancement.
    }
}

function securePage() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = 'login.html';
    }
}

async function displayUserInfo() {
    const token = localStorage.getItem('token');
    if (!token) {
        return;
    }

    const userId = getUserIdFromToken();
    if (!userId) {
        localStorage.removeItem('token');
        window.location.href = 'login.html';
        return;
    }

    try {
        const response = await fetch(`${USER_SERVICE_URL}/${userId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch user info');
        }
        const user = await response.json();

        const userGreeting = document.getElementById('user-greeting');
        if (userGreeting) {
            userGreeting.textContent = `Welcome, ${user.full_name}`;
        }
        const userAvatar = document.getElementById('user-avatar');
        if (userAvatar) {
            userAvatar.src = `https://avatar.vercel.sh/${user.email}.png`;
        }
    } catch (error) {
        console.error(error);
        localStorage.removeItem('token');
        window.location.href = 'login.html';
    }
}
