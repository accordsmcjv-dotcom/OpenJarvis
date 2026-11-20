import { registerPlugin } from '@capacitor/core';

export interface ShivamContact {
  name: string;
  number: string;
}

interface ContactsCallPlugin {
  findContacts(options: { query: string }): Promise<{ contacts: ShivamContact[]; count: number }>;
  placeCall(options: { number: string }): Promise<{ success: boolean; message: string }>;
}

const ContactsCall = registerPlugin<ContactsCallPlugin>('ContactsCall');

export const findShivamContacts = (query: string) => ContactsCall.findContacts({ query });
export const placeShivamCall = (number: string) => ContactsCall.placeCall({ number });
